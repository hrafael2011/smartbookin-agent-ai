"""
Cuando el negocio no tiene servicios activos, evitamos llamadas a OpenAI
y enrutamos por palabras clave hacia intents que los handlers resuelven sin lista de servicios.
"""
from typing import Dict


NO_SERVICES_GENERIC = (
    "Este negocio aún no tiene servicios cargados para reservar por aquí. "
    "Podés consultar horarios y ubicación en el menú (opción 5) o contactar al local directamente."
)

GREETING_NO_SERVICES = (
    "¡Hola! Este negocio todavía no publicó servicios para reservar por el chat. "
    "Podés ver horarios y ubicación con la opción 5 del menú o escribir al local."
)


def nlu_result_without_openai(message: str) -> Dict:
    """
    Resultado compatible con NLUEngine.process cuando no hay servicios en BD.
    Sin llamadas a la API.
    """
    t = (message or "").strip().lower()
    base = {
        "confidence": 0.92,
        "entities": {},
        "missing": [],
        "raw_understanding": "no_services_keyword_router",
        "response_text": "",
    }

    if any(
        k in t
        for k in (
            "ubicación",
            "ubicacion",
            "dirección",
            "direccion",
            "horario",
            "horarios",
            "donde",
            "dónde",
            "local",
            "llegar",
            "mapa",
        )
    ):
        return {**base, "intent": "business_info", "confidence": 0.95}

    if any(k in t for k in ("mis citas", "ver citas", "mis turnos", "qué citas", "que citas")):
        return {**base, "intent": "check_appointment", "confidence": 0.95}

    if any(k in t for k in ("cancelar", "cancelá", "anular")):
        return {**base, "intent": "cancel_appointment", "confidence": 0.9}

    if any(k in t for k in ("cambiar", "modificar", "reagendar", "mover la cita")):
        return {**base, "intent": "modify_appointment", "confidence": 0.88}

    if any(
        k in t
        for k in (
            "reservar",
            "agendar",
            "pedir turno",
            "quiero turno",
            "quiero cita",
            "una cita",
            "hacer cita",
            "sacar turno",
            "tomar turno",
        )
    ):
        return {
            **base,
            "intent": "clarification_needed",
            "confidence": 0.85,
            "response_text": NO_SERVICES_GENERIC,
        }

    if any(k in t for k in ("hola", "buenas", "hey", "qué tal", "que tal", "buenos días", "buenas tardes")):
        return {
            **base,
            "intent": "greeting",
            "confidence": 0.9,
            "response_text": GREETING_NO_SERVICES,
        }

    if len(t) <= 2 or t in ("ok", "gracias", "👍"):
        return {
            **base,
            "intent": "greeting",
            "confidence": 0.7,
            "response_text": GREETING_NO_SERVICES,
        }

    return {
        **base,
        "intent": "clarification_needed",
        "confidence": 0.6,
        "response_text": NO_SERVICES_GENERIC,
    }
