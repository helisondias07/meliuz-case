from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meliuz_abtest.data_loader import DataValidationError, REQUIRED_COLUMNS, load_dataset


def _write_csv(tmp_path: Path, rows: list[dict], columns: list[str] | None = None) -> Path:
    path = tmp_path / "dataset.csv"
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)
    return path


def _valid_row(group: str = "Grupo 1", date: str = "2026-01-01") -> dict:
    return {
        "Data": date,
        "Grupos de usuários": group,
        "Parceiro": "Parceiro Teste",
        "compradores": 10,
        "comissão": "R$ 1.000",
        "cashback": "R$ 100",
        "vendas totais": "R$ 10.000",
    }


@pytest.mark.parametrize(
    "dataset_name,expected_groups",
    [
        ("dataset_01_parceiroA.csv", 3),
        ("dataset_02_parceiroB.csv", 3),
        ("dataset_03_parceiroC.csv", 2),
    ],
)
def test_loads_real_datasets(dataset_name: str, expected_groups: int):
    df = load_dataset(ROOT_DIR / "data" / dataset_name)

    assert len(df) > 0
    assert df["Grupos de usuários"].nunique() == expected_groups
    assert set(REQUIRED_COLUMNS).issubset(df.columns)
    assert {"margem", "cashback_pct_vendas"}.issubset(df.columns)
    assert df.attrs["meta"]["linhas_invalidas_removidas"] == 0
    assert df.attrs["meta"]["linhas_duplicadas_removidas"] == 0


def test_missing_required_column_raises_clear_error(tmp_path: Path):
    row = _valid_row()
    row.pop("cashback")
    path = _write_csv(tmp_path, [row], columns=[column for column in REQUIRED_COLUMNS if column != "cashback"])

    with pytest.raises(DataValidationError, match="Colunas obrigatórias ausentes.*cashback"):
        load_dataset(path)


def test_mixed_money_formats_and_invalid_money_rows_are_counted(tmp_path: Path):
    rows = [
        {
            **_valid_row("Grupo 1", "2026-01-01"),
            "comissão": "R$1.234,56",
            "cashback": "R$ 1234",
            "vendas totais": "1234.56",
        },
        {
            **_valid_row("Grupo 2", "2026-01-01"),
            "comissão": "R$ 1234",
            "cashback": "R$1.234,56",
            "vendas totais": "R$ 1.234",
        },
        {**_valid_row("Grupo 2", "2026-01-02"), "comissão": "", "cashback": "R$ 10"},
        {**_valid_row("Grupo 1", "2026-01-02"), "cashback": "abc"},
    ]

    df = load_dataset(_write_csv(tmp_path, rows))

    assert len(df) == 2
    assert df.attrs["meta"]["linhas_invalidas_removidas"] == 2
    assert df.loc[df["Grupos de usuários"] == "Grupo 1", "comissão"].iloc[0] == pytest.approx(1234.56)
    assert df.loc[df["Grupos de usuários"] == "Grupo 1", "cashback"].iloc[0] == pytest.approx(1234.0)
    assert df.loc[df["Grupos de usuários"] == "Grupo 2", "cashback"].iloc[0] == pytest.approx(1234.56)


def test_exact_duplicate_rows_are_removed_and_counted(tmp_path: Path):
    row_a = _valid_row("Grupo 1", "2026-01-01")
    row_b = _valid_row("Grupo 2", "2026-01-01")
    path = _write_csv(tmp_path, [row_a, row_a.copy(), row_b])

    df = load_dataset(path)

    assert len(df) == 2
    assert df.attrs["meta"]["linhas_duplicadas_removidas"] == 1
    assert df.attrs["meta"]["linhas_removidas_limpeza"] == 1


def test_empty_or_null_group_rows_are_removed_and_counted(tmp_path: Path):
    rows = [
        _valid_row("Grupo 1", "2026-01-01"),
        _valid_row("Grupo 2", "2026-01-01"),
        _valid_row("", "2026-01-02"),
        {**_valid_row("Grupo 1", "2026-01-03"), "Grupos de usuários": None},
    ]

    df = load_dataset(_write_csv(tmp_path, rows))

    assert len(df) == 2
    assert df.attrs["meta"]["linhas_invalidas_removidas"] == 2
    assert sorted(df["Grupos de usuários"].unique().tolist()) == ["Grupo 1", "Grupo 2"]


def test_dataset_with_only_one_variant_is_rejected(tmp_path: Path):
    rows = [
        _valid_row("Grupo 1", "2026-01-01"),
        _valid_row("Grupo 1", "2026-01-02"),
    ]

    with pytest.raises(DataValidationError, match="apenas 1 variante.*ao menos 2 grupos"):
        load_dataset(_write_csv(tmp_path, rows))


def test_dataset_is_rejected_when_second_variant_is_fully_invalid_after_cleaning(tmp_path: Path):
    rows = [
        _valid_row("Grupo 1", "2026-01-01"),
        _valid_row("Grupo 1", "2026-01-02"),
        {**_valid_row("Grupo 2", "2026-01-01"), "comissão": "valor inválido"},
        {**_valid_row("Grupo 2", "2026-01-02"), "cashback": ""},
    ]

    with pytest.raises(DataValidationError, match="apenas 1 variante.*ao menos 2 grupos"):
        load_dataset(_write_csv(tmp_path, rows))


def test_extra_column_is_ignored_without_breaking(tmp_path: Path):
    rows = [
        {**_valid_row("Grupo 1", "2026-01-01"), "observacao": "campo extra"},
        {**_valid_row("Grupo 2", "2026-01-01"), "observacao": "campo extra"},
    ]

    df = load_dataset(_write_csv(tmp_path, rows, columns=REQUIRED_COLUMNS + ["observacao"]))

    assert "observacao" not in df.columns
    assert df.attrs["meta"]["colunas_extras_ignoradas"] == ["observacao"]
    assert len(df) == 2
