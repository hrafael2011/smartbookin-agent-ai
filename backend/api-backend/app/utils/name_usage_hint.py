"""Pistas para el NLU: uso natural del nombre del cliente (sin sonar repetitivo)."""
from typing import List, Optional


def name_usage_hint(customer_name: str, recent_messages: Optional[List] = None) -> str:
    """
    Añadir al bloque INFORMACIÓN DEL CLIENTE. Guía al modelo según el último mensaje del asistente.
    """
    if not customer_name or not str(customer_name).strip():
        return ""
    nm = str(customer_name).strip().lower()
    if nm == "cliente":
        return ""

    last_assistant_text = ""
    for m in reversed(recent_messages or []):
        if m.get("role") == "assistant":
            last_assistant_text = m.get("content") or ""
            break

    if not last_assistant_text:
        return (
            "\n\nUso del nombre en esta respuesta: podés incluir su nombre al saludar o "
            "al cerrar la idea principal, una vez, si encaja con el tono."
        )
    if nm in last_assistant_text.lower():
        return (
            "\n\nUso del nombre en esta respuesta: en tu mensaje anterior ya lo mencionaste; "
            "no repitas el nombre salvo en una confirmación importante o si cambia el tema."
        )
    return (
        "\n\nUso del nombre en esta respuesta: podés usar su nombre al inicio o al confirmar, "
        "una vez, si encaja."
    )
