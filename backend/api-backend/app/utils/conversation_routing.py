"""Router liviano para decidir menú guiado vs flujo directo vs IA."""
from __future__ import annotations

import re
from typing import Optional

# Palabras de comando / flujo: no deben guardarse como nombre de persona.
RESERVED_CUSTOMER_DISPLAY_NAMES = frozenset(
    {
        "cambiar",
        "cámbiar",
        "modificar",
        "reagendar",
        "cancelar",
        "cancelá",
        "menu",
        "menú",
        "agendar",
        "cita",
        "turno",
        "reservar",
        "start",
        "help",
        "ayuda",
        "hola",
        "ok",
        "si",
        "sí",
        "no",
        "gracias",
    }
)


def is_reserved_customer_display_name(name: str) -> bool:
    t = (name or "").strip().lower()
    if not t:
        return True
    if t in RESERVED_CUSTOMER_DISPLAY_NAMES:
        return True
    if len(t) <= 12 and t.replace(" ", "").isdigit():
        return True
    return False


def is_random_or_greeting(text: str) -> bool:
    t = str(text or "").strip().lower()
    if not t:
        return True
    if len(t) <= 2:
        return True
    basic = {
        "hola",
        "buenas",
        "hello",
        "hi",
        "holi",
        "ok",
        "oki",
        "gracias",
        "👍",
        "👌",
    }
    if t in basic:
        return True
    if re.fullmatch(r"[^\w\s]+", t):
        return True
    return False


def parse_menu_choice(text: str) -> Optional[str]:
    t = str(text or "").strip().lower()
    if t in {"menu", "menú", "ayuda", "help"}:
        return "menu"
    if t in {"1", "2", "3", "4", "5"}:
        return t
    return None


def is_affirmative(text: str) -> bool:
    t = str(text or "").strip().lower()
    yes_words = {
        "si",
        "sí",
        "sii",
        "yes",
        "ok",
        "oki",
        "dale",
        "de acuerdo",
        "claro",
    }
    return t in yes_words


def is_negative_reply(text: str) -> bool:
    """Respuesta clara de rechazo (confirmación cancelación / no gracias)."""
    t = str(text or "").strip().lower()
    if t in {"no", "nop", "noo", "nah", "👎"}:
        return True
    if t.startswith("no ") and len(t) < 40:
        return True
    return any(
        p in t
        for p in ("mejor no", "no gracias", "dejalo", "déjalo", "dejá", "cancelá eso")
    )


def is_short_confirmation_message(text: str) -> bool:
    """
    Mensaje corto tipo sí/no u ok; usar para evitar LLM en pasos awaiting_*_confirmation.
    """
    t = str(text or "").strip().lower()
    if not t or len(t) > 42:
        return False
    if is_affirmative(t) or is_negative_reply(t):
        return True
    if t in {"ok", "okay", "okey", "👍", "👌"}:
        return True
    if re.match(r"^(sí|si|no|ok|dale|confirmo|claro)[\s!.¡?]*$", t):
        return True
    return False


def classify_route(text: str) -> str:
    """
    Returns:
    - menu: menú explícito o saludo/random
    - direct: intención directa por keywords (sin gastar IA al inicio)
    - ai: ambiguo/abierto
    """
    t = str(text or "").strip().lower()
    if parse_menu_choice(t) or is_random_or_greeting(t):
        return "menu"

    direct_keywords = (
        "agendar",
        "cita",
        "turno",
        "reservar",
        "cancelar",
        "cambiar",
        "modificar",
        "horario",
        "ubicación",
        "direccion",
        "dirección",
        "disponible",
    )
    if any(k in t for k in direct_keywords):
        return "direct"

    return "ai"


def guided_menu(customer_name: str = "", *, returning: bool = False) -> str:
    if returning and customer_name:
        lead = f"¡Bienvenido de nuevo, <b>{customer_name}</b>! 👋"
    elif customer_name:
        lead = f"¡Hola, <b>{customer_name}</b>! 👋"
    else:
        lead = "¡Hola! 👋"
    return (
        f"{lead}\n\n"
        "Podés elegir una opción:\n"
        "1) Agendar cita\n"
        "2) Ver mis citas\n"
        "3) Cambiar cita\n"
        "4) Cancelar cita\n"
        "5) Horarios y ubicación\n\n"
        "También podés escribir tu pedido directo (ej. \"quiero cita mañana 10am\")."
    )
