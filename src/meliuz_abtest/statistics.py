"""
Bootstrap para estimar incerteza entre variantes do teste A/B.

A comparacao principal e a diferenca de margem por comprador contra a baseline.
Como margem por comprador e uma razao de totais, o bootstrap reamostra datas e
recalcula soma(margem) / soma(compradores) em cada iteracao. Como os grupos
rodam nas mesmas datas, usamos bootstrap pareado: o mesmo sorteio de datas e
aplicado a variante e baseline. Isso controla efeitos comuns de calendario
(fim de semana, sazonalidade, promocao do parceiro) que afetam todos os grupos.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from meliuz_abtest.metrics import GROUP_COLUMN, summarize_variants


MIN_DAYS_FOR_STABLE_BOOTSTRAP = 30
DEFAULT_BOOTSTRAP_ITERATIONS = 10_000


class NoViableBaselineError(ValueError):
    """Erro quando nenhuma variante tem margem positiva para servir de baseline."""


def pick_baseline(summary: pd.DataFrame) -> str:
    """Escolhe a baseline viavel de menor cashback sobre GMV.

    A baseline tambem precisa passar pelo guardrail de negocio. Comparar uma
    variante candidata contra um grupo com margem negativa produziria uma
    estatistica numericamente valida, mas sem sentido operacional.
    """
    viable = summary[summary["margem_total"] > 0]
    if viable.empty:
        raise NoViableBaselineError(
            "Não há variante com margem_total > 0 para usar como baseline."
        )
    return str(viable["cashback_pct_vendas"].idxmin())


def _daily_totals(df: pd.DataFrame) -> pd.DataFrame:
    working = df.copy()
    if "margem" not in working.columns:
        working["margem"] = working["comissão"] - working["cashback"]

    return (
        working.groupby([GROUP_COLUMN, "Data"], as_index=False)
        .agg(
            margem=("margem", "sum"),
            compradores=("compradores", "sum"),
        )
        .sort_values([GROUP_COLUMN, "Data"])
    )


def _margin_per_buyer_from_indices(
    group_days: pd.DataFrame,
    sampled_indices: np.ndarray,
) -> np.ndarray:
    margins = group_days["margem"].to_numpy(dtype=float)
    buyers = group_days["compradores"].to_numpy(dtype=float)

    sampled_margins = margins[sampled_indices].sum(axis=1)
    sampled_buyers = buyers[sampled_indices].sum(axis=1)

    with np.errstate(divide="ignore", invalid="ignore"):
        ratios = sampled_margins / sampled_buyers
    ratios[~np.isfinite(ratios)] = np.nan
    return ratios


def _same_dates_for_pairing(variant_days: pd.DataFrame, baseline_days: pd.DataFrame) -> bool:
    variant_dates = variant_days["Data"].tolist()
    baseline_dates = baseline_days["Data"].tolist()
    return variant_dates == baseline_dates


def compare_variants_to_baseline(
    df: pd.DataFrame,
    summary: pd.DataFrame | None = None,
    baseline: str | None = None,
    n_iterations: int = DEFAULT_BOOTSTRAP_ITERATIONS,
    seed: int | None = None,
) -> pd.DataFrame:
    """Compara cada variante contra a baseline via bootstrap por dia.

    Retorna diferenca media, intervalo de confianca 95% e a proporcao de
    iteracoes em que a variante supera a baseline. Essa proporcao e intuitiva
    para negocio: perto de 50% significa que a vantagem parece ruido.

    Quando variante e baseline tem exatamente as mesmas datas, usamos bootstrap
    pareado. Se as datas nao coincidirem, caimos para bootstrap independente:
    a estimativa fica mais conservadora, mas a automacao nao quebra em testes
    que nao foram rodados de forma perfeitamente concorrente.
    """
    if n_iterations <= 0:
        raise ValueError("n_iterations precisa ser maior que zero.")

    if summary is None:
        summary = summarize_variants(df)

    if baseline is None:
        baseline = pick_baseline(summary)
    daily = _daily_totals(df)
    rng = np.random.default_rng(seed)

    baseline_days = daily[daily[GROUP_COLUMN] == baseline].sort_values("Data")
    rows = []

    for variant in summary.index.astype(str):
        if variant == baseline:
            continue

        variant_days = daily[daily[GROUP_COLUMN] == variant].sort_values("Data")
        pairing_used = _same_dates_for_pairing(variant_days, baseline_days)

        if pairing_used:
            # O mesmo conjunto de indices e aplicado aos dois grupos. Esse
            # pareamento preserva o efeito comum de cada data e isola melhor a
            # diferenca real entre variantes.
            n_days = len(baseline_days)
            sampled_indices = rng.integers(0, n_days, size=(n_iterations, n_days))
            baseline_bootstrap = _margin_per_buyer_from_indices(baseline_days, sampled_indices)
            variant_bootstrap = _margin_per_buyer_from_indices(variant_days, sampled_indices)
        else:
            baseline_indices = rng.integers(
                0,
                len(baseline_days),
                size=(n_iterations, len(baseline_days)),
            )
            variant_indices = rng.integers(
                0,
                len(variant_days),
                size=(n_iterations, len(variant_days)),
            )
            baseline_bootstrap = _margin_per_buyer_from_indices(baseline_days, baseline_indices)
            variant_bootstrap = _margin_per_buyer_from_indices(variant_days, variant_indices)

        differences = variant_bootstrap - baseline_bootstrap
        finite_differences = differences[np.isfinite(differences)]

        if len(finite_differences) == 0:
            diff_mean = np.nan
            ci_low = np.nan
            ci_high = np.nan
            win_rate = np.nan
        else:
            diff_mean = float(np.mean(finite_differences))
            ci_low, ci_high = np.percentile(finite_differences, [2.5, 97.5])
            win_rate = float(np.mean(finite_differences > 0))

        n_days_variant = int(len(variant_days))
        n_days_baseline = int(len(baseline_days))
        rows.append(
            {
                "variante": variant,
                "vs_baseline": baseline,
                "dif_margem_por_comprador_media": round(diff_mean, 4),
                "ic95_low": round(float(ci_low), 4),
                "ic95_high": round(float(ci_high), 4),
                "prob_variante_supera_baseline": round(win_rate, 4),
                "n_dias_variante": n_days_variant,
                "n_dias_baseline": n_days_baseline,
                "pareamento_usado": bool(pairing_used),
                "amostra_pequena_lt30d": bool(
                    min(n_days_variant, n_days_baseline) < MIN_DAYS_FOR_STABLE_BOOTSTRAP
                ),
            }
        )

    return pd.DataFrame(rows)


__all__ = [
    "DEFAULT_BOOTSTRAP_ITERATIONS",
    "MIN_DAYS_FOR_STABLE_BOOTSTRAP",
    "NoViableBaselineError",
    "compare_variants_to_baseline",
    "pick_baseline",
]
