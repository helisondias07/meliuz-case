from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meliuz_abtest.decision import ACTION_KEEP_TESTING, ACTION_SCALE, make_decision


def _summary(rows: dict) -> pd.DataFrame:
    return pd.DataFrame.from_dict(rows, orient="index")


def _comparison(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_decision_scales_clear_statistically_robust_winner():
    summary = _summary(
        {
            "Grupo 1": {"margem_total": 1000.0, "margem_por_comprador": 10.0},
            "Grupo 2": {"margem_total": 1500.0, "margem_por_comprador": 15.0},
        }
    )
    comparison = _comparison(
        [
            {
                "variante": "Grupo 2",
                "vs_baseline": "Grupo 1",
                "dif_margem_por_comprador_media": 5.0,
                "ic95_low": 2.0,
                "ic95_high": 8.0,
                "prob_variante_supera_baseline": 0.99,
                "pareamento_usado": True,
                "amostra_pequena_lt30d": False,
            }
        ]
    )

    decision = make_decision(summary, comparison, baseline="Grupo 1")

    assert decision["acao"] == ACTION_SCALE
    assert decision["variante_recomendada"] == "Grupo 2"
    assert decision["confiavel_estatisticamente"] is True
    assert "Escalar Grupo 2" in decision["motivo"]


def test_decision_discards_negative_margin_variant_even_if_it_has_good_statistics():
    summary = _summary(
        {
            "Grupo 1": {"margem_total": 1000.0, "margem_por_comprador": 10.0},
            "Grupo 2": {"margem_total": -100.0, "margem_por_comprador": 20.0},
        }
    )
    comparison = _comparison(
        [
            {
                "variante": "Grupo 2",
                "vs_baseline": "Grupo 1",
                "dif_margem_por_comprador_media": 10.0,
                "ic95_low": 5.0,
                "ic95_high": 15.0,
                "prob_variante_supera_baseline": 1.0,
                "pareamento_usado": True,
                "amostra_pequena_lt30d": False,
            }
        ]
    )

    decision = make_decision(summary, comparison, baseline="Grupo 1")

    assert decision["acao"] == ACTION_KEEP_TESTING
    assert decision["variante_recomendada"] is None
    assert any("Grupo 2 tem margem total <= R$ 0" in alert for alert in decision["alertas"])


def test_decision_keeps_testing_when_sample_is_small():
    summary = _summary(
        {
            "Grupo 1": {"margem_total": 1000.0, "margem_por_comprador": 10.0},
            "Grupo 2": {"margem_total": 1500.0, "margem_por_comprador": 15.0},
        }
    )
    comparison = _comparison(
        [
            {
                "variante": "Grupo 2",
                "vs_baseline": "Grupo 1",
                "dif_margem_por_comprador_media": 5.0,
                "ic95_low": 2.0,
                "ic95_high": 8.0,
                "prob_variante_supera_baseline": 0.99,
                "pareamento_usado": True,
                "amostra_pequena_lt30d": True,
            }
        ]
    )

    decision = make_decision(summary, comparison, baseline="Grupo 1")

    assert decision["acao"] == ACTION_KEEP_TESTING
    assert decision["variante_recomendada"] is None
    assert any("Amostra pequena" in caveat for caveat in decision["ressalvas"])


def test_decision_keeps_testing_when_confidence_interval_crosses_zero():
    summary = _summary(
        {
            "Grupo 1": {"margem_total": 1000.0, "margem_por_comprador": 10.0},
            "Grupo 2": {"margem_total": 1800.0, "margem_por_comprador": 18.0},
        }
    )
    comparison = _comparison(
        [
            {
                "variante": "Grupo 2",
                "vs_baseline": "Grupo 1",
                "dif_margem_por_comprador_media": 8.0,
                "ic95_low": -1.0,
                "ic95_high": 17.0,
                "prob_variante_supera_baseline": 0.88,
                "pareamento_usado": True,
                "amostra_pequena_lt30d": False,
            }
        ]
    )

    decision = make_decision(summary, comparison, baseline="Grupo 1")

    assert decision["acao"] == ACTION_KEEP_TESTING
    assert decision["variante_recomendada"] is None
    assert any("IC95" in caveat and "inclui zero" in caveat for caveat in decision["ressalvas"])


def test_decision_uses_comparison_against_viable_baseline_when_low_cashback_variant_is_not_viable():
    summary = _summary(
        {
            "Grupo 1": {"margem_total": -50.0, "margem_por_comprador": -5.0},
            "Grupo 2": {"margem_total": 1000.0, "margem_por_comprador": 10.0},
            "Grupo 3": {"margem_total": 1800.0, "margem_por_comprador": 18.0},
        }
    )
    comparison = _comparison(
        [
            {
                "variante": "Grupo 3",
                "vs_baseline": "Grupo 2",
                "dif_margem_por_comprador_media": 8.0,
                "ic95_low": 3.0,
                "ic95_high": 12.0,
                "prob_variante_supera_baseline": 0.98,
                "pareamento_usado": True,
                "amostra_pequena_lt30d": False,
            }
        ]
    )

    decision = make_decision(summary, comparison, baseline="Grupo 2")

    assert decision["acao"] == ACTION_SCALE
    assert decision["variante_recomendada"] == "Grupo 3"
    assert any("Grupo 1 tem margem total <= R$ 0" in alert for alert in decision["alertas"])
    assert decision["evidencia_estatistica"]["vs_baseline"] == "Grupo 2"
