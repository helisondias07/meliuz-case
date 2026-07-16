from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meliuz_abtest.metrics import GROUP_COLUMN, summarize_variants
from meliuz_abtest.statistics import NoViableBaselineError, compare_variants_to_baseline, pick_baseline


COMMISSION_COLUMN = "comissão"


def _row(
    day: int,
    group: str,
    compradores: int,
    vendas: float,
    comissao: float,
    cashback: float,
) -> dict:
    return {
        "Data": f"2026-01-{day:02d}",
        GROUP_COLUMN: group,
        "compradores": compradores,
        "vendas totais": vendas,
        COMMISSION_COLUMN: comissao,
        "cashback": cashback,
    }


def test_bootstrap_finds_large_consistent_margin_per_buyer_advantage():
    rows = []
    for day in range(1, 31):
        rows.append(_row(day, "Grupo 1", 10, 1000.0, 120.0, 20.0))
        rows.append(_row(day, "Grupo 2", 10, 1000.0, 180.0, 30.0))

    df = pd.DataFrame(rows)
    summary = summarize_variants(df)
    comparison = compare_variants_to_baseline(df, summary, n_iterations=2_000, seed=42)

    assert pick_baseline(summary) == "Grupo 1"
    result = comparison.iloc[0]
    assert result["variante"] == "Grupo 2"
    assert result["vs_baseline"] == "Grupo 1"
    assert result["dif_margem_por_comprador_media"] == 5.0
    assert result["ic95_low"] > 4.9
    assert result["prob_variante_supera_baseline"] > 0.99
    assert bool(result["pareamento_usado"]) is True
    assert bool(result["amostra_pequena_lt30d"]) is False


def test_bootstrap_stays_near_fifty_percent_when_groups_are_similar_and_noisy():
    rows = []
    common_day_effects = [8, 12, 9, 11, 10, 10.5, 9.5, 11.5, 8.5, 12.5] * 3
    small_daily_differences = [-1, 1, -0.8, 0.8, -0.5, 0.5, -1.2, 1.2, -0.6, 0.6] * 3
    for day, (margin_per_buyer, daily_difference) in enumerate(
        zip(common_day_effects, small_daily_differences),
        start=1,
    ):
        rows.append(_row(day, "Grupo 1", 10, 1000.0, (margin_per_buyer * 10) + 20.0, 20.0))
        rows.append(
            _row(
                day,
                "Grupo 2",
                10,
                1000.0,
                ((margin_per_buyer + daily_difference) * 10) + 20.0,
                20.0,
            )
        )

    df = pd.DataFrame(rows)
    summary = summarize_variants(df)
    comparison = compare_variants_to_baseline(df, summary, n_iterations=2_000, seed=42)

    result = comparison.iloc[0]
    assert result["vs_baseline"] == "Grupo 1"
    assert abs(result["dif_margem_por_comprador_media"]) < 0.1
    assert result["ic95_low"] < 0 < result["ic95_high"]
    assert 0.4 <= result["prob_variante_supera_baseline"] <= 0.6
    assert bool(result["pareamento_usado"]) is True
    assert bool(result["amostra_pequena_lt30d"]) is False


def test_bootstrap_flags_small_samples_without_failing():
    rows = []
    for day in range(1, 6):
        rows.append(_row(day, "Grupo 1", 10, 1000.0, 120.0, 20.0))
        rows.append(_row(day, "Grupo 2", 10, 1000.0, 180.0, 30.0))

    df = pd.DataFrame(rows)
    comparison = compare_variants_to_baseline(df, n_iterations=500, seed=7)

    assert len(comparison) == 1
    assert bool(comparison.iloc[0]["amostra_pequena_lt30d"]) is True


def test_paired_bootstrap_controls_common_day_effect_better_than_independent_resampling():
    rows = []
    common_day_effects = [6, 7, 8, 9, 30, 32, 34, 6, 7, 8] * 3
    for day, margin_per_buyer in enumerate(common_day_effects, start=1):
        rows.append(
            _row(
                day,
                "Grupo 1",
                compradores=10,
                vendas=1000.0,
                comissao=(margin_per_buyer * 10) + 20.0,
                cashback=20.0,
            )
        )
        rows.append(
            _row(
                day,
                "Grupo 2",
                compradores=10,
                vendas=1000.0,
                comissao=((margin_per_buyer + 1) * 10) + 30.0,
                cashback=30.0,
            )
        )

    df = pd.DataFrame(rows)
    summary = summarize_variants(df)
    paired = compare_variants_to_baseline(df, summary, n_iterations=2_000, seed=123).iloc[0]

    independent_differences = _independent_bootstrap_differences_for_test(
        df,
        variant="Grupo 2",
        baseline="Grupo 1",
        n_iterations=2_000,
        seed=123,
    )
    independent_low, independent_high = np.percentile(independent_differences, [2.5, 97.5])
    independent_width = independent_high - independent_low
    paired_width = paired["ic95_high"] - paired["ic95_low"]

    assert paired["dif_margem_por_comprador_media"] == 1.0
    assert paired["ic95_low"] > 0
    assert bool(paired["pareamento_usado"]) is True
    assert paired_width < independent_width
    assert independent_width > 5


def test_bootstrap_falls_back_to_independent_resampling_when_dates_do_not_match():
    rows = [
        _row(1, "Grupo 1", 10, 1000.0, 120.0, 20.0),
        _row(2, "Grupo 1", 10, 1000.0, 120.0, 20.0),
        _row(3, "Grupo 1", 10, 1000.0, 120.0, 20.0),
        _row(2, "Grupo 2", 10, 1000.0, 180.0, 30.0),
        _row(3, "Grupo 2", 10, 1000.0, 180.0, 30.0),
        _row(4, "Grupo 2", 10, 1000.0, 180.0, 30.0),
    ]

    comparison = compare_variants_to_baseline(pd.DataFrame(rows), n_iterations=500, seed=11)

    assert len(comparison) == 1
    assert bool(comparison.iloc[0]["pareamento_usado"]) is False
    assert comparison.iloc[0]["dif_margem_por_comprador_media"] > 0


def test_pick_baseline_ignores_non_viable_low_cashback_variant():
    summary = pd.DataFrame.from_dict(
        {
            "Grupo 1": {
                "margem_total": -10.0,
                "cashback_pct_vendas": 1.0,
            },
            "Grupo 2": {
                "margem_total": 100.0,
                "cashback_pct_vendas": 3.0,
            },
            "Grupo 3": {
                "margem_total": 200.0,
                "cashback_pct_vendas": 5.0,
            },
        },
        orient="index",
    )

    assert pick_baseline(summary) == "Grupo 2"


def test_pick_baseline_raises_when_no_variant_is_viable():
    summary = pd.DataFrame.from_dict(
        {
            "Grupo 1": {"margem_total": 0.0, "cashback_pct_vendas": 1.0},
            "Grupo 2": {"margem_total": -50.0, "cashback_pct_vendas": 2.0},
        },
        orient="index",
    )

    try:
        pick_baseline(summary)
    except NoViableBaselineError as exc:
        assert "margem_total > 0" in str(exc)
    else:
        raise AssertionError("pick_baseline deveria rejeitar ausencia de variante viavel")


def _independent_bootstrap_differences_for_test(
    df: pd.DataFrame,
    variant: str,
    baseline: str,
    n_iterations: int,
    seed: int,
) -> np.ndarray:
    """Replica o bootstrap independente antigo para comparar no teste."""
    working = df.copy()
    working["margem"] = working[COMMISSION_COLUMN] - working["cashback"]
    daily = (
        working.groupby([GROUP_COLUMN, "Data"], as_index=False)
        .agg(margem=("margem", "sum"), compradores=("compradores", "sum"))
        .sort_values([GROUP_COLUMN, "Data"])
    )

    rng = np.random.default_rng(seed)
    baseline_days = daily[daily[GROUP_COLUMN] == baseline]
    variant_days = daily[daily[GROUP_COLUMN] == variant]

    baseline_indices = rng.integers(0, len(baseline_days), size=(n_iterations, len(baseline_days)))
    variant_indices = rng.integers(0, len(variant_days), size=(n_iterations, len(variant_days)))

    baseline_ratios = _ratio_from_indices_for_test(baseline_days, baseline_indices)
    variant_ratios = _ratio_from_indices_for_test(variant_days, variant_indices)
    return variant_ratios - baseline_ratios


def _ratio_from_indices_for_test(group_days: pd.DataFrame, indices: np.ndarray) -> np.ndarray:
    margins = group_days["margem"].to_numpy(dtype=float)
    buyers = group_days["compradores"].to_numpy(dtype=float)
    return margins[indices].sum(axis=1) / buyers[indices].sum(axis=1)
