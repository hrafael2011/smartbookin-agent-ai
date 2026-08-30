"""Normalización de teléfonos de canal: `tg:` intacto, E.164 → solo dígitos."""

from app.utils.channel_phone import (
    is_telegram_channel_phone,
    is_whatsapp_channel_phone,
    normalize_channel_phone,
)


def test_normalize_e164_strips_plus_spaces_and_dashes():
    assert normalize_channel_phone("+1 (809) 555-1234") == "18095551234"


def test_normalize_keeps_telegram_prefix_untouched():
    assert normalize_channel_phone("tg:123456789") == "tg:123456789"


def test_normalize_handles_empty_and_none():
    assert normalize_channel_phone("") == ""
    assert normalize_channel_phone(None) == ""


def test_normalize_strips_leading_and_trailing_whitespace():
    assert normalize_channel_phone("  18095551234  ") == "18095551234"


def test_is_whatsapp_channel_phone():
    assert is_whatsapp_channel_phone("18095551234") is True
    assert is_whatsapp_channel_phone("tg:123") is False
    assert is_whatsapp_channel_phone("") is False


def test_is_telegram_channel_phone_still_works():
    assert is_telegram_channel_phone("tg:123") is True
    assert is_telegram_channel_phone("18095551234") is False
