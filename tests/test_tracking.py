from __future__ import annotations

import csv
import sys
import types
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meliuz_abtest.tracking import (
    TRACKING_COLUMNS,
    build_tracking_row,
    log_test_result,
    write_tracking_csv,
    write_tracking_google_sheets,
)


def _row() -> dict:
    return build_tracking_row(
        "Cashback Teste",
        "Descricao",
        {
            "parceiro": "Parceiro X",
            "periodo_inicio": "2026-01-01",
            "periodo_fim": "2026-01-30",
            "grupos": ["Grupo 1", "Grupo 2"],
        },
        {
            "acao": "escalar",
            "variante_recomendada": "Grupo 2",
            "motivo": "Motivo claro.",
            "confiavel_estatisticamente": True,
        },
        "outputs/reports/cashback_teste.md",
        "outputs/results/cashback_teste.json",
    )


def test_write_tracking_csv_creates_header_and_row(tmp_path: Path):
    csv_path = tmp_path / "tracking" / "acompanhamento.csv"

    written = write_tracking_csv(_row(), csv_path)

    assert written == str(csv_path)
    with csv_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert rows[0]["nome_teste"] == "Cashback Teste"
    assert rows[0]["acao"] == "escalar"
    assert rows[0]["variante_recomendada"] == "Grupo 2"
    assert list(rows[0].keys()) == TRACKING_COLUMNS


def test_write_tracking_csv_replaces_legacy_header(tmp_path: Path):
    csv_path = tmp_path / "acompanhamento.csv"
    csv_path.write_text("nome_teste,resultado\nTeste antigo,ok\n", encoding="utf-8")

    write_tracking_csv(_row(), csv_path)

    with csv_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert list(rows[0].keys()) == TRACKING_COLUMNS
    assert len(rows) == 1
    assert rows[0]["nome_teste"] == "Cashback Teste"


def test_log_test_result_falls_back_to_csv_when_env_vars_are_missing(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("SHEET_ID", raising=False)

    result = log_test_result(
        "Cashback Teste",
        "Descricao",
        {"parceiro": "Parceiro X", "periodo_inicio": "2026-01-01", "periodo_fim": "2026-01-30", "grupos": []},
        {"acao": "manter_teste", "motivo": "Sem robustez.", "confiavel_estatisticamente": False},
        "relatorio.md",
        "resultado.json",
        csv_path=tmp_path / "acompanhamento.csv",
    )

    assert Path(result["csv_path"]).exists()
    assert result["google_sheets_written"] is False


def test_write_tracking_google_sheets_success_with_mock(monkeypatch):
    worksheet = FakeWorksheet()
    fake_sheet = FakeSheet(worksheet)
    fake_gspread = types.SimpleNamespace(authorize=lambda credentials: FakeClient(fake_sheet))
    fake_credentials = types.SimpleNamespace(
        from_service_account_file=lambda path, scopes: {"path": path, "scopes": scopes}
    )

    _install_fake_google_modules(monkeypatch, fake_gspread, fake_credentials)
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", "secrets/fake.json")
    monkeypatch.setenv("SHEET_ID", "sheet123")
    monkeypatch.setenv("SHEET_TAB_NAME", "acompanhamento")

    assert write_tracking_google_sheets(_row()) is True
    assert worksheet.rows[0] == TRACKING_COLUMNS
    assert worksheet.rows[1][TRACKING_COLUMNS.index("nome_teste")] == "Cashback Teste"


def test_write_tracking_google_sheets_failure_is_captured(monkeypatch, capsys):
    fake_gspread = types.SimpleNamespace(authorize=lambda credentials: None)
    fake_credentials = types.SimpleNamespace(
        from_service_account_file=lambda path, scopes: (_ for _ in ()).throw(RuntimeError("credencial inválida"))
    )

    _install_fake_google_modules(monkeypatch, fake_gspread, fake_credentials)
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", "secrets/fake.json")
    monkeypatch.setenv("SHEET_ID", "sheet123")

    assert write_tracking_google_sheets(_row()) is False
    assert "Aviso" in capsys.readouterr().out


def _install_fake_google_modules(monkeypatch, fake_gspread, fake_credentials):
    google_module = types.ModuleType("google")
    oauth2_module = types.ModuleType("google.oauth2")
    service_account_module = types.ModuleType("google.oauth2.service_account")
    service_account_module.Credentials = fake_credentials

    monkeypatch.setitem(sys.modules, "gspread", fake_gspread)
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.oauth2", oauth2_module)
    monkeypatch.setitem(sys.modules, "google.oauth2.service_account", service_account_module)


class FakeWorksheet:
    def __init__(self):
        self.rows = []

    def get_all_values(self):
        return self.rows

    def append_row(self, row):
        self.rows.append(row)


class FakeSheet:
    def __init__(self, worksheet):
        self._worksheet = worksheet

    def worksheet(self, name):
        return self._worksheet

    def add_worksheet(self, title, rows, cols):
        return self._worksheet


class FakeClient:
    def __init__(self, sheet):
        self._sheet = sheet

    def open_by_key(self, sheet_id):
        return self._sheet
