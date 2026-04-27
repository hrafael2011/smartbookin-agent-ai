"""Utilidades robustas para interpretar horas de mensajes de usuario."""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple


def slot_hhmm(slot: Dict) -> str:
    start_dt = str(slot.get("start_datetime") or "")
    if "T" in start_dt and len(start_dt) >= 16:
        return start_dt[11:16]
    start_time = str(slot.get("start_time") or "").strip().lower()
    m = re.search(r"(\d{1,2}):(\d{2})", start_time)
    if m:
        hh = int(m.group(1))
        mm = int(m.group(2))
        if "pm" in start_time and hh < 12:
            hh += 12
        if "am" in start_time and hh == 12:
            hh = 0
        return f"{hh:02d}:{mm:02d}"
    return ""


def _to_hhmm(hour: int, minute: int) -> Optional[str]:
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"
    return None


def parse_time_candidates(raw: str, allow_bare_hour: bool = False) -> List[str]:
    """
    Extrae horas candidatas de un texto en formatos comunes:
    - 10, 10am, 10:30, 10:30pm
    - 15:00
    - "10 de la mañana", "3 de la tarde", "8 de la noche"
    """
    text = str(raw or "").strip().lower()
    out: List[str] = []

    # 1) hh:mm [am|pm]
    for h, m, suf in re.findall(r"\b(\d{1,2}):(\d{2})\s*(am|pm)?\b", text):
        hh = int(h)
        mm = int(m)
        if suf == "pm" and hh < 12:
            hh += 12
        if suf == "am" and hh == 12:
            hh = 0
        cand = _to_hhmm(hh, mm)
        if cand:
            out.append(cand)

    # 2) hh [am|pm]
    for h, suf in re.findall(r"\b(\d{1,2})\s*(am|pm)\b", text):
        hh = int(h)
        if suf == "pm" and hh < 12:
            hh += 12
        if suf == "am" and hh == 12:
            hh = 0
        cand = _to_hhmm(hh, 0)
        if cand:
            out.append(cand)

    # 3) hh de la mañana/tarde/noche
    dayparts = re.findall(
        r"\b(\d{1,2})(?::(\d{2}))?\s*(?:de la|de)\s*(mañana|tarde|noche)\b",
        text,
    )
    for h, m, part in dayparts:
        hh = int(h)
        mm = int(m) if m else 0
        if part in ("tarde", "noche") and hh < 12:
            hh += 12
        if part == "mañana" and hh == 12:
            hh = 0
        cand = _to_hhmm(hh, mm)
        if cand:
            out.append(cand)

    # 4) número suelto (opcional, útil cuando YA estamos pidiendo hora)
    if allow_bare_hour and not out:
        m = re.search(r"\b(\d{1,2})\b", text)
        if m:
            hh = int(m.group(1))
            # Heurística razonable para "10" sin sufijo: 10:00
            cand = _to_hhmm(hh, 0)
            if cand:
                out.append(cand)

    # dedupe preserving order
    seen = set()
    unique = []
    for val in out:
        if val not in seen:
            seen.add(val)
            unique.append(val)
    return unique


def pick_exact_slot(
    slots: List[Dict],
    requested_time: str,
    allow_bare_hour: bool = False,
) -> Optional[Dict]:
    candidates = parse_time_candidates(requested_time, allow_bare_hour=allow_bare_hour)
    if not candidates:
        return None
    by_hhmm = {slot_hhmm(s): s for s in slots}
    for cand in candidates:
        if cand in by_hhmm:
            return by_hhmm[cand]
    return None


def sort_slots_by_requested_time(
    slots: List[Dict],
    requested_time: str,
    preferred_hhmm: Optional[str] = None,
    allow_bare_hour: bool = False,
) -> List[Dict]:
    candidates = parse_time_candidates(requested_time, allow_bare_hour=allow_bare_hour)
    if not candidates:
        return slots

    target = candidates[0]
    try:
        th, tm = target.split(":")
        target_minutes = int(th) * 60 + int(tm)
    except Exception:
        return slots

    pref_minutes = None
    if preferred_hhmm and ":" in preferred_hhmm:
        try:
            ph, pm = preferred_hhmm.split(":")
            pref_minutes = int(ph) * 60 + int(pm)
        except Exception:
            pref_minutes = None

    def distance(slot: Dict) -> Tuple[int, int, str]:
        hhmm = slot_hhmm(slot)
        try:
            h, m = hhmm.split(":")
            mins = int(h) * 60 + int(m)
            d_req = abs(mins - target_minutes)
            d_pref = abs(mins - pref_minutes) if pref_minutes is not None else 0
            return (d_req, d_pref, hhmm)
        except Exception:
            return (9999, 9999, hhmm)

    return sorted(slots, key=distance)


def daypart_preference_hhmm_range(raw: str) -> Optional[Tuple[str, str]]:
    """
    Si el texto indica mañana/tarde/noche/primera hora, devuelve (inicio, fin) en HH:MM para filtrar slots.
    """
    text = str(raw or "").strip().lower()
    if not text:
        return None
    if any(
        p in text
        for p in (
            "primera hora",
            "primer horario",
            "a primera hora",
            "temprano",
            "al abrir",
            "apertura",
        )
    ):
        return ("06:00", "10:30")
    if any(p in text for p in ("en la mañana", "la mañana", "por la mañana")):
        return ("06:00", "12:00")
    if any(p in text for p in ("en la tarde", "la tarde", "por la tarde")):
        return ("12:00", "18:00")
    if any(p in text for p in ("en la noche", "la noche", "por la noche")):
        return ("18:00", "22:00")
    if "después del almuerzo" in text or "despues del almuerzo" in text:
        return ("14:00", "20:00")
    return None


def filter_slots_by_hhmm_range(
    slots: List[Dict], start_hhmm: str, end_hhmm: str
) -> List[Dict]:
    def mins(hhmm: str) -> int:
        h, m = hhmm.split(":")
        return int(h) * 60 + int(m)

    lo, hi = mins(start_hhmm), mins(end_hhmm)
    out = []
    for s in slots:
        sh = slot_hhmm(s)
        if not sh:
            continue
        try:
            v = mins(sh)
        except Exception:
            continue
        if lo <= v <= hi:
            out.append(s)
    return out if out else slots
