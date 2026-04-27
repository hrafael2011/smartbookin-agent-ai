"""
Textos de respuesta controlados (sin lógica de negocio ni LLM).
"""
from __future__ import annotations

FALLBACK_LOW_CONFIDENCE = (
    "No estoy seguro de entender. Puedo ayudarte con: "
    "<b>agendar una cita</b>, <b>ver tus citas</b>, <b>cancelar</b>, "
    "<b>cambiar fecha u hora</b> o <b>info del negocio</b>. ¿Qué necesitás?"
)

EMPTY_REPLY_PLACEHOLDER = "…"
