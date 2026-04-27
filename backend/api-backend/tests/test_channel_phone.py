from app.utils.channel_phone import is_telegram_channel_phone


def test_telegram_prefix():
    assert is_telegram_channel_phone("tg:12345") is True
    assert is_telegram_channel_phone("+18095551234") is False
    assert is_telegram_channel_phone("") is False
