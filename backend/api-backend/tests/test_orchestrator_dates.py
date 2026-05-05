"""Autoridad de fechas en el orchestrator (sin LLM)."""
from datetime import date, timedelta

from app.core import orchestrator as orch
from app.utils.date_parse import (
    DEFAULT_OPERATIONAL_TIMEZONE,
    format_month_label,
    format_week_label,
    resolve_date_from_spanish_text,
)


def test_apply_python_date_authority_from_date_raw():
    nlu = {"entities": {"date_raw": "viernes"}}
    orch._apply_python_date_authority(nlu, "quiero el viernes")
    assert nlu["entities"].get("date")
    assert len(nlu["entities"]["date"]) == 10


def test_apply_python_date_authority_fixes_mismatch_iso():
    nlu = {"entities": {"date": "2026-04-08"}}  # miércoles si fuera incoherente con "viernes"
    orch._apply_python_date_authority(nlu, "me refiero el viernes")
    assert nlu["entities"]["date"] != "2026-04-08"


def test_relative_date_parser_uses_santo_domingo_operational_timezone():
    assert DEFAULT_OPERATIONAL_TIMEZONE == "America/Santo_Domingo"


# --- Tests spec 004 T003: fix "para hoy" y variantes ---

def test_date_parse_para_hoy():
    today = date.today()
    result = resolve_date_from_spanish_text("para hoy", today=today)
    assert result == today.strftime("%Y-%m-%d")


def test_date_parse_hoy_con_hora():
    today = date.today()
    result = resolve_date_from_spanish_text("hoy a las 3", today=today)
    assert result == today.strftime("%Y-%m-%d")


def test_date_parse_reservar_para_hoy():
    today = date.today()
    result = resolve_date_from_spanish_text("reservar para hoy", today=today)
    assert result == today.strftime("%Y-%m-%d")


def test_date_parse_manana_con_contexto():
    today = date.today()
    tomorrow = today + timedelta(days=1)
    result = resolve_date_from_spanish_text("para mañana en la tarde", today=today)
    assert result == tomorrow.strftime("%Y-%m-%d")


def test_date_parse_manana_sin_tilde():
    today = date.today()
    tomorrow = today + timedelta(days=1)
    result = resolve_date_from_spanish_text("quiero cita manana", today=today)
    assert result == tomorrow.strftime("%Y-%m-%d")


def test_date_parse_hoy_exacto_sigue_funcionando():
    today = date.today()
    result = resolve_date_from_spanish_text("hoy", today=today)
    assert result == today.strftime("%Y-%m-%d")


def test_calendar_week_label_same_month():
    assert format_week_label(date(2026, 6, 1), date(2026, 6, 7)) == "Semana del 1 al 7"


def test_calendar_month_label():
    assert format_month_label(2026, 6) == "Junio 2026"
