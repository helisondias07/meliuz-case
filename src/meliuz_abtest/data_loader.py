"""
Carregamento e limpeza dos CSVs de teste A/B de cashback.

Este modulo concentra as regras de qualidade de dados antes de qualquer
analise de negocio. A ideia e separar problemas recuperaveis (linha duplicada,
valor monetario invalido em uma linha) de problemas estruturais (schema errado,
menos de duas variantes), que impedem uma comparacao A/B defensavel.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = [
    "Data",
    "Grupos de usuários",
    "Parceiro",
    "compradores",
    "comissão",
    "cashback",
    "vendas totais",
]

MONEY_COLUMNS = ["comissão", "cashback", "vendas totais"]
ESSENTIAL_COLUMNS = [
    "Data",
    "Grupos de usuários",
    "Parceiro",
    "compradores",
    "comissão",
    "cashback",
    "vendas totais",
]


class DataValidationError(Exception):
    """Erro de validacao de schema ou de qualidade que impede a analise."""


def _parse_money(value) -> float:
    """Converte dinheiro em formatos comuns do CSV para float.

    Aceitamos formatos mistos porque bases operacionais costumam chegar com
    pequenas variacoes ("R$1.234,56", "R$ 1234", "1234.56"). Quando o valor
    nao e interpretavel, devolvemos NaN para a linha ser descartada com contador
    explicito, em vez de mascarar o problema como zero.
    """
    if pd.isna(value):
        return float("nan")

    text = str(value).strip()
    if not text:
        return float("nan")

    text = text.replace("R$", "").strip()
    text = re.sub(r"\s+", "", text)

    if re.fullmatch(r"[+-]?\d{1,3}(\.\d{3})+,\d{1,2}", text):
        normalized = text.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"[+-]?\d+,\d{1,2}", text):
        normalized = text.replace(",", ".")
    elif re.fullmatch(r"[+-]?\d{1,3}(\.\d{3})+", text):
        normalized = text.replace(".", "")
    elif re.fullmatch(r"[+-]?\d+(\.\d+)?", text):
        normalized = text
    else:
        return float("nan")

    try:
        return float(normalized)
    except ValueError:
        return float("nan")


def load_dataset(path: str | Path) -> pd.DataFrame:
    """Carrega, valida e limpa um dataset de teste A/B.

    Retorna um DataFrame apenas com as colunas esperadas e campos derivados
    usados nos proximos modulos. Contadores de limpeza ficam em df.attrs["meta"]
    para aparecerem depois no relatorio de forma transparente.
    """
    path = Path(path)

    try:
        df = pd.read_csv(path)
    except Exception as exc:
        raise DataValidationError(f"Não foi possível ler o arquivo '{path}': {exc}") from exc

    df.columns = [str(column).strip() for column in df.columns]

    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise DataValidationError(
            f"Colunas obrigatórias ausentes em '{path}': {missing}. "
            f"Colunas encontradas: {list(df.columns)}"
        )

    original_rows = len(df)
    extra_columns = [column for column in df.columns if column not in REQUIRED_COLUMNS]

    # Colunas extras nao devem quebrar a automacao: o schema fixo define o que
    # entra na analise e qualquer informacao adicional fica fora para evitar
    # dependencia acidental de campos que nao existem em todos os testes.
    df = df[REQUIRED_COLUMNS].copy()

    duplicate_mask = df.duplicated(keep="first")
    duplicate_rows = int(duplicate_mask.sum())
    df = df.loc[~duplicate_mask].copy()

    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    df["Grupos de usuários"] = df["Grupos de usuários"].astype("string").str.strip()
    df["Parceiro"] = df["Parceiro"].astype("string").str.strip()
    df["compradores"] = pd.to_numeric(df["compradores"], errors="coerce")

    for column in MONEY_COLUMNS:
        df[column] = df[column].apply(_parse_money)

    empty_text_mask = (
        df["Grupos de usuários"].isna()
        | df["Grupos de usuários"].eq("")
        | df["Parceiro"].isna()
        | df["Parceiro"].eq("")
    )
    null_mask = df[ESSENTIAL_COLUMNS].isna().any(axis=1)
    invalid_rows_mask = empty_text_mask | null_mask
    invalid_rows = int(invalid_rows_mask.sum())
    df = df.loc[~invalid_rows_mask].copy()

    if df.empty:
        raise DataValidationError(f"'{path}' ficou sem linhas válidas após a limpeza.")

    group_count = df["Grupos de usuários"].nunique()
    if group_count < 2:
        raise DataValidationError(
            f"'{path}' tem apenas {group_count} variante(s) após limpeza. "
            "Um teste A/B precisa de ao menos 2 grupos para comparação."
        )

    df["margem"] = df["comissão"] - df["cashback"]
    df["cashback_pct_vendas"] = (df["cashback"] / df["vendas totais"]).replace(
        [float("inf"), -float("inf")],
        float("nan"),
    ) * 100

    meta = {
        "arquivo": str(path),
        "linhas_originais": original_rows,
        "linhas_duplicadas_removidas": duplicate_rows,
        "linhas_invalidas_removidas": invalid_rows,
        "linhas_removidas_limpeza": duplicate_rows + invalid_rows,
        "linhas_validas": len(df),
        "colunas_extras_ignoradas": extra_columns,
        "parceiro": df["Parceiro"].iloc[0] if df["Parceiro"].nunique() == 1 else "múltiplos",
        "grupos": sorted(df["Grupos de usuários"].unique().tolist()),
        "periodo_inicio": df["Data"].min().date().isoformat(),
        "periodo_fim": df["Data"].max().date().isoformat(),
        "dias_por_grupo": df.groupby("Grupos de usuários").size().to_dict(),
    }
    df.attrs["meta"] = meta

    return df


__all__ = ["DataValidationError", "REQUIRED_COLUMNS", "load_dataset", "_parse_money"]
