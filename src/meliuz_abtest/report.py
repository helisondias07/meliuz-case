"""
Geracao de relatorio para gestor e JSON estruturado para consumo futuro.

O Markdown e o artefato humano: resume decisao, tabelas e grafico. O JSON e o
artefato de maquina: facilita a Fase 2 do dashboard sem precisar parsear texto.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from meliuz_abtest.decision import ACTION_KEEP_TESTING, ACTION_SCALE


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "teste_ab"


def generate_report(
    test_name: str,
    description: str,
    meta: dict,
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    decision: dict,
    reports_dir: str | Path = "outputs/reports",
    results_dir: str | Path = "outputs/results",
) -> dict:
    """Gera Markdown, grafico PNG e JSON estruturado do teste."""
    reports_dir = Path(reports_dir)
    results_dir = Path(results_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    slug = slugify(test_name)
    chart_path = reports_dir / f"{slug}_chart.png"
    markdown_path = reports_dir / f"{slug}.md"
    json_path = results_dir / f"{slug}.json"

    _make_chart(summary, chart_path, test_name, decision)
    markdown_path.write_text(
        _render_markdown(test_name, description, meta, summary, comparison, decision, chart_path),
        encoding="utf-8",
    )
    json_path.write_text(
        json.dumps(
            _structured_result(test_name, description, meta, summary, comparison, decision, chart_path, markdown_path),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "markdown_path": str(markdown_path),
        "chart_path": str(chart_path),
        "json_path": str(json_path),
    }


def _make_chart(summary: pd.DataFrame, chart_path: Path, test_name: str, decision: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    groups = summary.index.astype(str).tolist()
    colors = _variant_colors(summary, decision)

    axes[0].bar(groups, summary["margem_por_comprador"], color=colors)
    axes[0].set_title("Margem por comprador")
    axes[0].set_ylabel("R$")
    axes[0].tick_params(axis="x", rotation=20)

    axes[1].bar(groups, summary["compradores_total"], color="#5B6C8F")
    axes[1].set_title("Compradores totais")
    axes[1].tick_params(axis="x", rotation=20)

    fig.suptitle(test_name)
    fig.tight_layout()
    fig.savefig(chart_path, dpi=140)
    plt.close(fig)


def _render_markdown(
    test_name: str,
    description: str,
    meta: dict,
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    decision: dict,
    chart_path: Path,
) -> str:
    lines = [
        f"# Relatório de Teste A/B - {test_name}",
        "",
        "## Resumo executivo",
        "",
        f"**Decisão:** {_decision_label(decision)}",
        "",
        decision["motivo"],
        "",
    ]

    if description:
        lines.extend([f"**Descrição:** {description}", ""])

    lines.extend(
        [
            f"**Parceiro:** {meta.get('parceiro', 'não informado')}  ",
            f"**Período:** {meta.get('periodo_inicio', 'n/d')} a {meta.get('periodo_fim', 'n/d')}  ",
            f"**Variantes:** {', '.join(meta.get('grupos', []))}  ",
            f"**Dias por variante:** {meta.get('dias_por_grupo', {})}",
            "",
        ]
    )

    if decision.get("alertas"):
        lines.extend(["### Alertas críticos", ""])
        lines.extend([f"- **Atenção:** {alert}" for alert in decision["alertas"]])
        lines.append("")

    if decision.get("ressalvas"):
        lines.extend(["### Ressalvas", ""])
        lines.extend([f"- {caveat}" for caveat in decision["ressalvas"]])
        lines.append("")

    lines.extend(
        [
            "## Resumo por variante",
            "",
            summary.to_markdown(),
            "",
            f"![Comparativo de margem e volume]({chart_path.name})",
            "",
            "## Comparação estatística",
            "",
            "Métrica comparada: diferença de margem por comprador contra a baseline. "
            "O critério de decisão é o IC95 excluir zero; a taxa de vitória no bootstrap "
            "é exibida apenas como leitura intuitiva.",
            "",
        ]
    )

    if comparison.empty:
        lines.extend(["_Sem comparação estatística disponível._", ""])
    else:
        display = comparison.copy()
        if "pareamento_usado" in display.columns:
            display["tipo_bootstrap"] = display["pareamento_usado"].map(
                {True: "pareado por data", False: "independente"}
            )
        lines.extend([display.to_markdown(index=False), ""])

    lines.extend(
        [
            "## Qualidade dos dados",
            "",
            f"- Linhas originais: {meta.get('linhas_originais', 'n/d')}",
            f"- Linhas válidas: {meta.get('linhas_validas', 'n/d')}",
            f"- Linhas removidas na limpeza: {meta.get('linhas_removidas_limpeza', 0)}",
            f"- Duplicatas removidas: {meta.get('linhas_duplicadas_removidas', 0)}",
            f"- Linhas inválidas removidas: {meta.get('linhas_invalidas_removidas', 0)}",
            f"- Colunas extras ignoradas: {meta.get('colunas_extras_ignoradas', [])}",
            "",
        ]
    )

    return "\n".join(lines)


def _decision_label(decision: dict) -> str:
    if decision.get("acao") == ACTION_SCALE:
        return f"Escalar {decision.get('variante_recomendada')} para 100% do tráfego"
    return "Não escalar ainda; manter teste"


def _variant_colors(summary: pd.DataFrame, decision: dict) -> list[str]:
    """Define cores do grafico sem contradizer a decisao final.

    Verde significa confirmacao para escalar, entao so aparece quando a regra
    final recomenda escala. Lider observada sem robustez estatistica recebe
    ambar, que comunica "candidata" sem sugerir vencedora confirmada.
    """
    confirmed = (
        decision.get("acao") == ACTION_SCALE
        and decision.get("variante_recomendada") is not None
    )
    recommended = str(decision.get("variante_recomendada")) if confirmed else None
    viable = summary[summary["margem_total"] > 0]
    candidate = (
        str(viable["margem_por_comprador"].idxmax())
        if decision.get("acao") == ACTION_KEEP_TESTING and not viable.empty
        else None
    )

    colors = []
    for group, row in summary.iterrows():
        group_name = str(group)
        if row["margem_total"] <= 0:
            colors.append("#C92A2A")
        elif confirmed and group_name == recommended:
            colors.append("#2F6F6D")
        elif candidate and group_name == candidate:
            colors.append("#B7791F")
        else:
            colors.append("#8A94A6")
    return colors


def _structured_result(
    test_name: str,
    description: str,
    meta: dict,
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    decision: dict,
    chart_path: Path,
    markdown_path: Path,
) -> dict[str, Any]:
    return {
        "test_name": test_name,
        "description": description,
        "meta": _json_safe(meta),
        "summary": _records_with_index(summary, "variante"),
        "comparison": _json_safe(comparison.to_dict(orient="records")),
        "decision": _json_safe(decision),
        "artifacts": {
            "markdown_path": str(markdown_path),
            "chart_path": str(chart_path),
        },
    }


def _records_with_index(df: pd.DataFrame, index_name: str) -> list[dict]:
    records = []
    for index, row in df.iterrows():
        record = {index_name: index}
        record.update(row.to_dict())
        records.append(record)
    return _json_safe(records)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        return _json_safe(value.item())
    if not isinstance(value, (list, dict, tuple)):
        try:
            if pd.isna(value):
                return None
        except TypeError:
            pass
    return value


__all__ = ["generate_report", "slugify"]
