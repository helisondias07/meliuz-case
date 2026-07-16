from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meliuz_abtest.metrics import summarize_variants


def test_summarize_variants_calculates_expected_values_for_two_groups():
    df = pd.DataFrame(
        [
            {
                "Data": "2026-01-01",
                "Grupos de usuários": "Grupo 1",
                "compradores": 10,
                "vendas totais": 1000.0,
                "comissão": 100.0,
                "cashback": 20.0,
            },
            {
                "Data": "2026-01-02",
                "Grupos de usuários": "Grupo 1",
                "compradores": 20,
                "vendas totais": 2000.0,
                "comissão": 200.0,
                "cashback": 40.0,
            },
            {
                "Data": "2026-01-01",
                "Grupos de usuários": "Grupo 2",
                "compradores": 5,
                "vendas totais": 500.0,
                "comissão": 50.0,
                "cashback": 25.0,
            },
            {
                "Data": "2026-01-02",
                "Grupos de usuários": "Grupo 2",
                "compradores": 15,
                "vendas totais": 1500.0,
                "comissão": 150.0,
                "cashback": 75.0,
            },
        ]
    )

    summary = summarize_variants(df)

    grupo_1 = summary.loc["Grupo 1"]
    assert grupo_1["compradores_total"] == 30
    assert grupo_1["dias"] == 2
    assert grupo_1["vendas_total"] == 3000.0
    assert grupo_1["comissao_total"] == 300.0
    assert grupo_1["cashback_total"] == 60.0
    assert grupo_1["margem_total"] == 240.0
    assert grupo_1["margem_por_comprador"] == 8.0
    assert grupo_1["ticket_medio"] == 100.0
    assert grupo_1["cashback_pct_vendas"] == 2.0
    assert grupo_1["roi_cashback"] == 4.0

    grupo_2 = summary.loc["Grupo 2"]
    assert grupo_2["compradores_total"] == 20
    assert grupo_2["dias"] == 2
    assert grupo_2["vendas_total"] == 2000.0
    assert grupo_2["comissao_total"] == 200.0
    assert grupo_2["cashback_total"] == 100.0
    assert grupo_2["margem_total"] == 100.0
    assert grupo_2["margem_por_comprador"] == 5.0
    assert grupo_2["ticket_medio"] == 100.0
    assert grupo_2["cashback_pct_vendas"] == 5.0
    assert grupo_2["roi_cashback"] == 1.0


def test_zero_margin_does_not_create_invalid_ratios():
    df = pd.DataFrame(
        [
            {
                "Data": "2026-01-01",
                "Grupos de usuários": "Grupo 1",
                "compradores": 10,
                "vendas totais": 1000.0,
                "comissão": 100.0,
                "cashback": 100.0,
            },
            {
                "Data": "2026-01-01",
                "Grupos de usuários": "Grupo 2",
                "compradores": 20,
                "vendas totais": 2000.0,
                "comissão": 300.0,
                "cashback": 100.0,
            },
        ]
    )

    summary = summarize_variants(df)
    grupo_1 = summary.loc["Grupo 1"]

    assert grupo_1["margem_total"] == 0.0
    assert grupo_1["margem_por_comprador"] == 0.0
    assert grupo_1["cashback_pct_vendas"] == 10.0
    assert grupo_1["roi_cashback"] == 0.0
    assert grupo_1.replace([float("inf"), -float("inf")], pd.NA).notna().all()


def test_zero_denominator_ratios_return_nan_instead_of_infinity():
    df = pd.DataFrame(
        [
            {
                "Data": "2026-01-01",
                "Grupos de usuários": "Grupo 1",
                "compradores": 0,
                "vendas totais": 0.0,
                "comissão": 0.0,
                "cashback": 0.0,
            },
            {
                "Data": "2026-01-01",
                "Grupos de usuários": "Grupo 2",
                "compradores": 1,
                "vendas totais": 100.0,
                "comissão": 20.0,
                "cashback": 10.0,
            },
        ]
    )

    summary = summarize_variants(df)
    grupo_1 = summary.loc["Grupo 1"]

    assert pd.isna(grupo_1["margem_por_comprador"])
    assert pd.isna(grupo_1["ticket_medio"])
    assert pd.isna(grupo_1["cashback_pct_vendas"])
    assert pd.isna(grupo_1["roi_cashback"])
    assert summary.replace([float("inf"), -float("inf")], pd.NA).equals(summary)
