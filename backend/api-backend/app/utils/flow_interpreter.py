"""
Interpretación local de mensajes dentro del flujo de reserva (sin LLM).
Corrige fechas/horas y evita falsos cambios de intención.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from app.utils.date_parse import resolve_date_from_spanish_text
from app.utils.time_parser import daypart_preference_hhmm_range, parse_time_candidates


def user_message_looks_like_booking_correction(text: str) -> bool:
    """True si el usuario está corrigiendo fecha/hora, no pidiendo otra cosa."""
    t = (text or "").lower()
    markers = (
        "me refiero",
        "quiero decir",
        "no es",
        "no mañana",
        "no manana",
        "perdón",
        "perdon",
        "disculp",
        "corrijo",
        "equivoc",
        "no es mañana",
        "próximo",
        "proximo",
        "el lunes",
        "el martes",
        "el miércoles",
        "el miercoles",
        "el jueves",
        "el viernes",
    )
    if any(m in t for m in markers):
        return True
    if re.search(
        r"\b(lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo)\b",
        t,
    ):
        return True
    return False


def try_booking_flow_synthetic_nlu(
    *,
    state: str,
    raw_text: str,
    pending_data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Si podemos interpretar el mensaje como datos del flujo de reserva, devolvemos
    un nlu_result sintético (intent book_appointment) y el pipeline no debe
    romper el flujo por intents check/cancel/modify.
    """
    if state not in (
        "awaiting_service",
        "awaiting_date",
        "awaiting_time",
        "awaiting_name",
        "awaiting_slot_selection",
    ):
        return None

    text = (raw_text or "").strip()
    if not text:
        return None

    entities: Dict[str, Any] = {}
    iso = resolve_date_from_spanish_text(text)
    if iso:
        entities["date"] = iso
        entities["date_raw"] = text

    # Preferencia de franja horaria ("a primera hora", "en la mañana")
    dr = daypart_preference_hhmm_range(text)
    if dr:
        entities["time_daypart_range"] = {"start": dr[0], "end": dr[1]}

    tc = parse_time_candidates(text, allow_bare_hour=state == "awaiting_time")
    if tc:
        entities["time"] = tc[0]

    if not entities:
        return None

    # awaiting_slot_selection: corrección de fecha o refinamiento de franja/hora sin LLM
    if state == "awaiting_slot_selection":
        prev = pending_data.get("date")
        if iso and prev and iso != prev:
            return {
                "intent": "book_appointment",
                "confidence": 0.95,
                "entities": entities,
                "missing": [],
                "raw_understanding": "flow_interpreter_date_correction",
                "response_text": "",
                "flow_stay_in_booking": True,
                "_from_flow_interpreter": True,
            }
        if prev and (dr or tc) and (not iso or iso == prev):
            return {
                "intent": "book_appointment",
                "confidence": 0.92,
                "entities": entities,
                "missing": [],
                "raw_understanding": "flow_interpreter_slot_refinement",
                "response_text": "",
                "flow_stay_in_booking": True,
                "_from_flow_interpreter": True,
            }

    if state in ("awaiting_date", "awaiting_time") and (iso or tc or dr):
        return {
            "intent": "book_appointment",
            "confidence": 0.9,
            "entities": entities,
            "missing": [],
            "raw_understanding": "flow_interpreter_datetime",
            "response_text": "",
            "flow_stay_in_booking": True,
            "_from_flow_interpreter": True,
        }

    return None
