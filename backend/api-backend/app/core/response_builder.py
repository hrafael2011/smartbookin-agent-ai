"""
Textos de respuesta controlados (sin lógica de negocio ni LLM).
"""
from __future__ import annotations

from typing import Dict, List, Optional

FALLBACK_LOW_CONFIDENCE = (
    "No estoy seguro de entender. Puedo ayudarte con: "
    "<b>agendar una cita</b>, <b>ver tus citas</b>, <b>cancelar</b>, "
    "<b>cambiar fecha u hora</b> o <b>info del negocio</b>. ¿Qué necesitás?"
)

EMPTY_REPLY_PLACEHOLDER = "…"

# Fila de teclado inline: lista de botones {text, callback_data}.
KeyboardRow = List[Dict[str, str]]


class BotReply(str):
    """Respuesta del bot: texto + teclado inline opcional.

    Es una subclase de ``str`` para compatibilidad total con el código existente
    (comparaciones de strings, run_conversation_turn -> str, canal WhatsApp).
    El teclado es una lista de filas, cada fila una lista de botones
    ``{"text": "...", "callback_data": "..."}`` (Telegram Inline Keyboard).
    """

    keyboard: Optional[KeyboardRow]

    def __new__(cls, text: str, keyboard: Optional[KeyboardRow] = None) -> "BotReply":
        obj = str.__new__(cls, text)
        obj.keyboard = keyboard
        return obj
