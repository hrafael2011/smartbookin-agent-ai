"""Identificadores de canal en el campo `phone_number` de cliente/contexto."""


def is_telegram_channel_phone(phone_number: str) -> bool:
    """True si el valor corresponde al prefijo usado para usuarios de Telegram."""
    return bool(phone_number) and phone_number.startswith("tg:")
