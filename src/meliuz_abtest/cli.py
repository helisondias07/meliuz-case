"""
Ponto de entrada unico da solucao de analise A/B.

Uso:
    python -m meliuz_abtest.cli --input data/dataset_01_parceiroA.csv \
        --test-name "Cashback Parceiro A" \
        --description "Teste de cashback no Parceiro A"
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd

from meliuz_abtest.data_loader import DataValidationError, load_dataset
from meliuz_abtest.decision import ACTION_KEEP_TESTING, make_decision
from meliuz_abtest.metrics import summarize_variants
from meliuz_abtest.report import generate_report
from meliuz_abtest.statistics import NoViableBaselineError, compare_variants_to_baseline, pick_baseline
from meliuz_abtest.tracking import log_test_result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analisa um teste A/B de cashback do Méliuz.")
    parser.add_argument("--input", required=True, help="Caminho do CSV do teste A/B.")
    parser.add_argument("--test-name", required=True, help="Nome curto do teste.")
    parser.add_argument("--description", default="", help="Descrição breve do teste.")
    parser.add_argument("--reports-dir", default="outputs/reports", help="Pasta dos relatórios Markdown/PNG.")
    parser.add_argument("--results-dir", default="outputs/results", help="Pasta dos JSONs estruturados.")
    parser.add_argument(
        "--tracking-csv",
        default="outputs/tracking/acompanhamento.csv",
        help="CSV de acompanhamento consolidado.",
    )
    parser.add_argument("--bootstrap-iterations", type=int, default=10_000, help="Iterações do bootstrap.")
    parser.add_argument("--seed", type=int, default=42, help="Seed do bootstrap para reprodutibilidade.")
    args = parser.parse_args(argv)

    try:
        df = load_dataset(args.input)
    except DataValidationError as exc:
        print(f"[ERRO] {exc}", file=sys.stderr)
        return 1

    summary = summarize_variants(df)
    meta = df.attrs.get("meta", {})

    try:
        baseline = pick_baseline(summary)
        comparison = compare_variants_to_baseline(
            df,
            summary=summary,
            baseline=baseline,
            n_iterations=args.bootstrap_iterations,
            seed=args.seed,
        )
        decision = make_decision(summary, comparison, baseline)
    except NoViableBaselineError as exc:
        baseline = None
        comparison = pd.DataFrame()
        decision = {
            "acao": ACTION_KEEP_TESTING,
            "variante_recomendada": None,
            "motivo": (
                "Não escalar ainda; nenhuma variante teve margem total positiva. "
                "O desenho do teste deve ser revisado antes de direcionar 100% do tráfego."
            ),
            "alertas": [str(exc)],
            "ressalvas": ["Todas as variantes foram descartadas pelo guardrail de margem."],
            "confiavel_estatisticamente": False,
        }

    artifacts = generate_report(
        args.test_name,
        args.description,
        meta,
        summary,
        comparison,
        decision,
        reports_dir=args.reports_dir,
        results_dir=args.results_dir,
    )
    tracking = log_test_result(
        args.test_name,
        args.description,
        meta,
        decision,
        artifacts["markdown_path"],
        artifacts["json_path"],
        csv_path=args.tracking_csv,
    )

    _print_summary(artifacts, tracking, baseline, decision)
    return 0


def _print_summary(artifacts: dict, tracking: dict, baseline: str | None, decision: dict) -> None:
    print(f"Relatório gerado em: {artifacts['markdown_path']}")
    print(f"JSON gerado em:      {artifacts['json_path']}")
    print(f"Log CSV atualizado:  {tracking['csv_path']}")
    print(f"Google Sheets:       {'atualizado' if tracking['google_sheets_written'] else 'não configurado / pulado'}")
    print(f"Baseline:            {baseline or 'nenhuma variante viável'}")
    print()
    print(f"Ação: {decision['acao']}")
    print(f"Variante recomendada: {decision.get('variante_recomendada') or 'NENHUMA'}")
    print(f"Motivo: {decision['motivo']}")
    for alert in decision.get("alertas", []):
        print(f"ALERTA: {alert}")
    for caveat in decision.get("ressalvas", []):
        print(f"RESSALVA: {caveat}")


if __name__ == "__main__":
    raise SystemExit(main())
