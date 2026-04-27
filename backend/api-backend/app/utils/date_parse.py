"""Parseo de fechas en español y formato legible para el usuario."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional

_WEEKDAYS = {
    "lunes": 0,
    "martes": 1,
    "miércoles": 2,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sábado": 5,
    "sabado": 5,
    "domingo": 6,
}

_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def _next_weekday_from_today(target_weekday: int, today: Optional[date] = None) -> date:
    today = today or date.today()
    days_ahead = (target_weekday - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


def resolve_date_from_spanish_text(text: str, today: Optional[date] = None) -> Optional[str]:
    """
    Devuelve YYYY-MM-DD si el texto contiene una fecha interpretable.
    Prioriza día de la semana ("próximo lunes", "el martes").
    """
    if not text or not str(text).strip():
        return None
    today = today or date.today()
    t = str(text).lower().strip()

    if t in ("hoy", "today"):
        return today.strftime("%Y-%m-%d")
    if t in ("mañana", "manana", "tomorrow"):
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    if "pasado mañana" in t or "pasado manana" in t:
        return (today + timedelta(days=2)).strftime("%Y-%m-%d")

    for day_name, widx in _WEEKDAYS.items():
        if day_name not in t:
            continue
        days_ahead = (widx - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        d = today + timedelta(days=days_ahead)
        return d.strftime("%Y-%m-%d")

    # "10 de abril", "5 de diciembre"
    m = re.search(
        r"\b(\d{1,2})\s+de\s+(" + "|".join(_MONTHS.keys()) + r")\b",
        t,
        re.I,
    )
    if m:
        day_num = int(m.group(1))
        month_name = m.group(2).lower()
        month = _MONTHS.get(month_name)
        if month and 1 <= day_num <= 31:
            year = today.year
            try:
                candidate = date(year, month, day_num)
            except ValueError:
                return None
            if candidate < today:
                try:
                    candidate = date(year + 1, month, day_num)
                except ValueError:
                    return None
            return candidate.strftime("%Y-%m-%d")

    return None


def weekday_mismatch(iso_date: str, user_text: str) -> bool:
    """True si el usuario menciona un día de la semana y la fecha ISO no coincide."""
    if not iso_date or len(iso_date) != 10:
        return False
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d").date()
    except ValueError:
        return False
    t = (user_text or "").lower()
    for name, widx in _WEEKDAYS.items():
        if name in t and d.weekday() != widx:
            return True
    return False


def format_date_human_es(iso_date: str) -> str:
    """Ej: 2026-04-13 → 'lunes 13 de abril'."""
    if not iso_date or len(iso_date) != 10:
        return iso_date or ""
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d").date()
    except ValueError:
        return iso_date
    names = (
        "lunes",
        "martes",
        "miércoles",
        "jueves",
        "viernes",
        "sábado",
        "domingo",
    )
    months = (
        "",
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    )
    return f"{names[d.weekday()]} {d.day} de {months[d.month]}"
