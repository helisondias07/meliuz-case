"""
Registro consolidado dos testes analisados.

O CSV e sempre escrito primeiro porque ele e o fallback garantido do case. O
Google Sheets e uma integracao adicional: se credenciais/env vars existirem,
tentamos escrever la tambem; se falhar, avisamos e seguimos com o CSV salvo.
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path


TRACKING_COLUMNS = [
    "data_registro",
    "nome_teste",
    "descricao",
    "parceiro",
    "periodo",
    "variantes",
    "acao",
    "variante_recomendada",
    "motivo",
    "confiavel_estatisticamente",
    "caminho_relatorio",
    "caminho_json",
]


def build_tracking_row(
    test_name: str,
    description: str,
    meta: dict,
    decision: dict,
    report_path: str,
    json_path: str,
) -> dict:
    return {
        "data_registro": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "nome_teste": test_name,
        "descricao": description,
        "parceiro": meta.get("parceiro", ""),
        "periodo": f"{meta.get('periodo_inicio', '')} a {meta.get('periodo_fim', '')}",
        "variantes": ", ".join(meta.get("grupos", [])),
        "acao": decision.get("acao", ""),
        "variante_recomendada": decision.get("variante_recomendada") or "",
        "motivo": decision.get("motivo", ""),
        "confiavel_estatisticamente": decision.get("confiavel_estatisticamente", False),
        "caminho_relatorio": report_path,
        "caminho_json": json_path,
    }


def log_test_result(
    test_name: str,
    description: str,
    meta: dict,
    decision: dict,
    report_path: str,
    json_path: str,
    csv_path: str | Path = "outputs/tracking/acompanhamento.csv",
) -> dict:
    """Registra o teste em CSV e, se configurado, tambem no Google Sheets."""
    row = build_tracking_row(test_name, description, meta, decision, report_path, json_path)
    csv_written = write_tracking_csv(row, csv_path)
    sheets_written = write_tracking_google_sheets(row)
    return {
        "csv_path": csv_written,
        "google_sheets_written": sheets_written,
    }


def write_tracking_csv(row: dict, csv_path: str | Path = "outputs/tracking/acompanhamento.csv") -> str:
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = csv_path.exists()
    mode = "a"

    if file_exists and csv_path.stat().st_size > 0:
        with csv_path.open("r", newline="", encoding="utf-8") as file:
            current_header = next(csv.reader(file), [])
        if current_header != TRACKING_COLUMNS:
            mode = "w"

    with csv_path.open(mode, newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=TRACKING_COLUMNS)
        if mode == "w" or not file_exists or csv_path.stat().st_size == 0:
            writer.writeheader()
        writer.writerow({column: row.get(column, "") for column in TRACKING_COLUMNS})

    return str(csv_path)


def write_tracking_google_sheets(row: dict) -> bool:
    creds_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    sheet_id = os.environ.get("SHEET_ID")
    tab_name = os.environ.get("SHEET_TAB_NAME", "acompanhamento")

    if not creds_path or not sheet_id:
        return False

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials = Credentials.from_service_account_file(creds_path, scopes=scopes)
        client = gspread.authorize(credentials)
        sheet = client.open_by_key(sheet_id)
        worksheet = _get_or_create_worksheet(sheet, tab_name)

        if not worksheet.get_all_values():
            worksheet.append_row(TRACKING_COLUMNS)
        worksheet.append_row([str(row.get(column, "")) for column in TRACKING_COLUMNS])
        return True
    except Exception as exc:
        print(
            f"[tracking] Aviso: não foi possível escrever no Google Sheets ({exc}). "
            "O CSV local foi mantido normalmente."
        )
        return False


def _get_or_create_worksheet(sheet, tab_name: str):
    try:
        return sheet.worksheet(tab_name)
    except Exception:
        return sheet.add_worksheet(title=tab_name, rows=1000, cols=len(TRACKING_COLUMNS))


__all__ = [
    "TRACKING_COLUMNS",
    "build_tracking_row",
    "log_test_result",
    "write_tracking_csv",
    "write_tracking_google_sheets",
]
