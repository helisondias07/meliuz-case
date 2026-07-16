"""
Metricas de negocio por variante do teste A/B.

O case pergunta qual variante escalar, entao este modulo evita olhar apenas
volume bruto. A metrica principal e margem por comprador: ela conecta receita
liquida com eficiencia por usuario comprador e reduz o risco de escolher uma
variante que vende mais apenas porque queimou cashback demais.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


GROUP_COLUMN = "Grupos de usuários"

SUMMARY_COLUMNS = [
    "compradores_total",
    "dias",
    "vendas_total",
    "comissao_total",
    "cashback_total",
    "margem_total",
    "margem_por_comprador",
    "ticket_medio",
    "cashback_pct_vendas",
    "roi_cashback",
]


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Divide series evitando infinito quando o denominador e zero.

    Quando o denominador e zero, a razao nao tem interpretacao economica
    confiavel; usamos NaN em vez de infinito para nao poluir a decisao.
    """
    numerator = numerator.astype(float)
    denominator = denominator.astype(float)
    return numerator.div(denominator).replace([np.inf, -np.inf], np.nan)


def summarize_variants(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega as metricas de negocio por variante.

    `margem_por_comprador` e a principal candidata para a regra de decisao,
    porque mede quanto sobra para o Meliuz por comprador depois de pagar o
    cashback. GMV e compradores continuam no resumo como contexto de volume.
    """
    working = df.copy()
    working["margem"] = working["comissão"] - working["cashback"]

    summary = working.groupby(GROUP_COLUMN).agg(
        compradores_total=("compradores", "sum"),
        dias=("Data", "count"),
        vendas_total=("vendas totais", "sum"),
        comissao_total=("comissão", "sum"),
        cashback_total=("cashback", "sum"),
        margem_total=("margem", "sum"),
    )

    summary["margem_por_comprador"] = _safe_divide(
        summary["margem_total"],
        summary["compradores_total"],
    )
    summary["ticket_medio"] = _safe_divide(
        summary["vendas_total"],
        summary["compradores_total"],
    )
    summary["cashback_pct_vendas"] = _safe_divide(
        summary["cashback_total"],
        summary["vendas_total"],
    ) * 100
    summary["roi_cashback"] = _safe_divide(
        summary["margem_total"],
        summary["cashback_total"],
    )

    return summary[SUMMARY_COLUMNS].round(2)


__all__ = ["SUMMARY_COLUMNS", "summarize_variants"]
