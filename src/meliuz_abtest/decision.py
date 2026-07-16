"""
Regra de decisao para escalar ou manter um teste A/B de cashback.

A decisao combina guardrails de negocio com robustez estatistica. O criterio
estatistico principal e o IC95 da diferenca de margem por comprador excluir
zero. A probabilidade de vitoria no bootstrap e mantida como leitura intuitiva
para o relatorio, mas nao decide sozinha.
"""

from __future__ import annotations

import pandas as pd


ACTION_SCALE = "escalar"
ACTION_KEEP_TESTING = "manter_teste"


def _format_currency_brl(value: float) -> str:
    """Formata moeda no padrao brasileiro sem depender do locale do sistema."""
    absolute = abs(float(value))
    formatted = f"{absolute:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    prefix = "-R$" if value < 0 else "R$"
    return f"{prefix} {formatted}"


def make_decision(summary: pd.DataFrame, comparison: pd.DataFrame, baseline: str) -> dict:
    """Retorna a recomendacao final do teste.

    Regra:
    1. Variantes com margem_total <= 0 sao descartadas.
    2. Entre as viaveis, a lider e a maior margem_por_comprador.
    3. A lider so escala se a evidencia for robusta: IC95 exclui zero e
       amostra >= 30 dias por grupo.
    4. Caso contrario, a recomendacao e manter o teste.
    """
    alerts = _margin_alerts(summary)
    viable = summary[summary["margem_total"] > 0]

    if viable.empty:
        return {
            "acao": ACTION_KEEP_TESTING,
            "variante_recomendada": None,
            "motivo": (
                "Não escalar ainda; nenhuma variante teve margem total positiva. "
                "O desenho do teste deve ser revisado antes de direcionar 100% do tráfego."
            ),
            "alertas": alerts,
            "ressalvas": ["Todas as variantes foram descartadas pelo guardrail de margem."],
            "confiavel_estatisticamente": False,
        }

    leader = str(viable["margem_por_comprador"].idxmax())
    leader_margin = float(viable.loc[leader, "margem_por_comprador"])
    leader_margin_formatted = _format_currency_brl(leader_margin)

    robust, caveats, evidence = _statistical_evidence_for_leader(leader, baseline, comparison)
    if robust:
        return {
            "acao": ACTION_SCALE,
            "variante_recomendada": leader,
            "motivo": (
                f"Escalar {leader} para 100% do tráfego. A variante tem a maior margem "
                f"por comprador entre as opções viáveis ({leader_margin_formatted}) e a "
                "diferença é estatisticamente robusta pelo IC95 do bootstrap."
            ),
            "alertas": alerts,
            "ressalvas": caveats,
            "evidencia_estatistica": evidence,
            "confiavel_estatisticamente": True,
        }

    return {
        "acao": ACTION_KEEP_TESTING,
        "variante_recomendada": None,
        "motivo": (
            f"Não escalar ainda; manter teste. {leader} tem a maior margem por comprador "
            f"observada ({leader_margin_formatted}), mas a evidência estatística ainda não "
            "é suficiente para mover 100% do tráfego com segurança."
        ),
        "alertas": alerts,
        "ressalvas": caveats,
        "evidencia_estatistica": evidence,
        "confiavel_estatisticamente": False,
    }


def _margin_alerts(summary: pd.DataFrame) -> list[str]:
    alerts = []
    non_positive = summary[summary["margem_total"] <= 0]
    for variant, row in non_positive.iterrows():
        alerts.append(
            f"{variant} tem margem total <= R$ 0,00 ({_format_currency_brl(row['margem_total'])}). "
            "Essa variante queima receita e não deve ser escalada, independentemente "
            "de volume ou resultado estatístico."
        )
    return alerts


def _statistical_evidence_for_leader(
    leader: str,
    baseline: str,
    comparison: pd.DataFrame,
) -> tuple[bool, list[str], dict]:
    if comparison.empty:
        return False, ["Não há comparação estatística disponível contra a baseline."], {}

    if leader == baseline:
        return _baseline_evidence(comparison, baseline)

    row = comparison[comparison["variante"] == leader]
    if row.empty:
        return (
            False,
            [f"Não há linha de bootstrap comparando {leader} contra a baseline {baseline}."],
            {},
        )

    evidence = _evidence_from_row(row.iloc[0])
    caveats = _common_caveats(row.iloc[0])

    # Para uma variante acima da baseline, o IC95 precisa ficar inteiro acima
    # de zero. Se cruza zero, a diferenca observada pode ser ruido.
    ci_excludes_zero_positive = evidence["ic95_low"] > 0
    if not ci_excludes_zero_positive:
        caveats.append(
            "O IC95 da diferença de margem por comprador inclui zero; a vantagem "
            "observada pode ser ruído."
        )

    robust = ci_excludes_zero_positive and not bool(row.iloc[0]["amostra_pequena_lt30d"])
    return robust, caveats, evidence


def _baseline_evidence(comparison: pd.DataFrame, baseline: str) -> tuple[bool, list[str], dict]:
    caveats = []
    if comparison["amostra_pequena_lt30d"].astype(bool).any():
        caveats.append("Amostra pequena: pelo menos uma comparação tem menos de 30 dias por grupo.")

    viable_comparisons = comparison.dropna(subset=["ic95_high"])
    if viable_comparisons.empty:
        return False, ["Não há IC95 válido para comparar alternativas contra a baseline."], {}

    # Quando a lider e a propria baseline, ela so e robusta se todas as outras
    # variantes viaveis tiverem IC95 inteiramente abaixo de zero contra ela.
    all_alternatives_worse = (viable_comparisons["ic95_high"] < 0).all()
    if not all_alternatives_worse:
        caveats.append(
            f"{baseline} lidera a métrica observada, mas pelo menos uma alternativa "
            "não é estatisticamente pior pelo IC95."
        )

    evidence = {
        "baseline": baseline,
        "alternativas_comparadas": int(len(viable_comparisons)),
    }
    robust = all_alternatives_worse and not comparison["amostra_pequena_lt30d"].astype(bool).any()
    return robust, caveats, evidence


def _evidence_from_row(row: pd.Series) -> dict:
    return {
        "variante": row["variante"],
        "vs_baseline": row["vs_baseline"],
        "dif_margem_por_comprador_media": float(row["dif_margem_por_comprador_media"]),
        "ic95_low": float(row["ic95_low"]),
        "ic95_high": float(row["ic95_high"]),
        "prob_variante_supera_baseline": float(row["prob_variante_supera_baseline"]),
        "pareamento_usado": bool(row.get("pareamento_usado", False)),
    }


def _common_caveats(row: pd.Series) -> list[str]:
    caveats = []
    if bool(row["amostra_pequena_lt30d"]):
        caveats.append("Amostra pequena: comparação tem menos de 30 dias por grupo.")
    if not bool(row.get("pareamento_usado", True)):
        caveats.append(
            "As datas entre variante e baseline não coincidem; foi usado bootstrap "
            "independente, uma estimativa mais conservadora."
        )
    return caveats


__all__ = ["ACTION_KEEP_TESTING", "ACTION_SCALE", "make_decision"]
