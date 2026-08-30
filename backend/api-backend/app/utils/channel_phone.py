"""Identificadores de canal en el campo `phone_number` de cliente/contexto."""


def is_telegram_channel_phone(phone_number: str) -> bool:
    """True si el valor corresponde al prefijo usado para usuarios de Telegram."""
    return bool(phone_number) and phone_number.startswith("tg:")


def is_whatsapp_channel_phone(phone_number: str) -> bool:
    """True si el valor es un teléfono de WhatsApp (E.164) y no un id de Telegram."""
    return bool(phone_number) and not is_telegram_channel_phone(phone_number)


def normalize_channel_phone(phone_number) -> str:
    """Normaliza un identificador de canal para lookup y guardado:
    `tg:...` intacto; E.164/legacy → solo dígitos (quita +, espacios, guiones, paréntesis).
    """
    p = str(phone_number or "").strip()
    if not p or p.startswith("tg:"):
        return p
    return "".join(ch for ch in p if ch.isdigit())
