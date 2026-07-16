from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meliuz_abtest.decision import ACTION_KEEP_TESTING, ACTION_SCALE
from meliuz_abtest.report import _variant_colors, generate_report, slugify


def test_generate_report_writes_markdown_chart_and_structured_json(tmp_path: Path):
    summary = pd.DataFrame.from_dict(
        {
            "Grupo 1": {
                "compradores_total": 100,
                "dias": 30,
                "vendas_total": 10000.0,
                "comissao_total": 1000.0,
                "cashback_total": 200.0,
                "margem_total": 800.0,
                "margem_por_comprador": 8.0,
                "ticket_medio": 100.0,
                "cashback_pct_vendas": 2.0,
                "roi_cashback": 4.0,
            },
            "Grupo 2": {
                "compradores_total": 120,
                "dias": 30,
                "vendas_total": 12000.0,
                "comissao_total": 1500.0,
                "cashback_total": 300.0,
                "margem_total": 1200.0,
                "margem_por_comprador": 10.0,
                "ticket_medio": 100.0,
                "cashback_pct_vendas": 2.5,
                "roi_cashback": 4.0,
            },
        },
        orient="index",
    )
    comparison = pd.DataFrame(
        [
            {
                "variante": "Grupo 2",
                "vs_baseline": "Grupo 1",
                "dif_margem_por_comprador_media": 2.0,
                "ic95_low": 0.5,
                "ic95_high": 3.5,
                "prob_variante_supera_baseline": 0.96,
                "n_dias_variante": 30,
                "n_dias_baseline": 30,
                "pareamento_usado": True,
                "amostra_pequena_lt30d": False,
            }
        ]
    )
    decision = {
        "acao": ACTION_SCALE,
        "variante_recomendada": "Grupo 2",
        "motivo": "Escalar Grupo 2 para 100% do tráfego.",
        "alertas": [],
        "ressalvas": [],
        "confiavel_estatisticamente": True,
    }
    meta = {
        "parceiro": "Parceiro Teste",
        "periodo_inicio": "2026-01-01",
        "periodo_fim": "2026-01-30",
        "grupos": ["Grupo 1", "Grupo 2"],
        "dias_por_grupo": {"Grupo 1": 30, "Grupo 2": 30},
        "linhas_originais": 60,
        "linhas_validas": 60,
    }

    paths = generate_report(
        "Cashback Parceiro Teste",
        "Teste automatizado",
        meta,
        summary,
        comparison,
        decision,
        reports_dir=tmp_path / "reports",
        results_dir=tmp_path / "results",
    )

    markdown = Path(paths["markdown_path"])
    chart = Path(paths["chart_path"])
    json_path = Path(paths["json_path"])

    assert markdown.exists()
    assert chart.exists()
    assert json_path.exists()
    assert chart.stat().st_size > 0

    markdown_text = markdown.read_text(encoding="utf-8")
    assert "Relatório de Teste A/B" in markdown_text
    assert "Escalar Grupo 2" in markdown_text
    assert "pareado por data" in markdown_text

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["test_name"] == "Cashback Parceiro Teste"
    assert payload["summary"][0]["variante"] == "Grupo 1"
    assert payload["comparison"][0]["pareamento_usado"] is True
    assert payload["decision"]["variante_recomendada"] == "Grupo 2"


def test_slugify_has_stable_ascii_filenames():
    assert slugify("Cashback Parceiro A") == "cashback_parceiro_a"
    assert slugify("  Teste -- 01  ") == "teste_01"


def test_chart_colors_do_not_mark_winner_green_when_decision_is_keep_testing():
    summary = pd.DataFrame.from_dict(
        {
            "Grupo 1": {"margem_total": 100.0, "margem_por_comprador": 5.0},
            "Grupo 2": {"margem_total": 200.0, "margem_por_comprador": 10.0},
            "Grupo 3": {"margem_total": -10.0, "margem_por_comprador": 20.0},
        },
        orient="index",
    )
    decision = {
        "acao": ACTION_KEEP_TESTING,
        "variante_recomendada": None,
    }

    colors = _variant_colors(summary, decision)

    assert "#2F6F6D" not in colors
    assert colors == ["#8A94A6", "#B7791F", "#C92A2A"]
