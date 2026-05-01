"""Autoridad de fechas en el orchestrator (sin LLM)."""
from app.core import orchestrator as orch
from app.utils.date_parse import DEFAULT_OPERATIONAL_TIMEZONE


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
