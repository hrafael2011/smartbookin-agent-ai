from app.services.telegram_link_service import generate_invite_token, tg_chat_key


def test_tg_chat_key_format():
    assert tg_chat_key("999") == "tg:999"


def test_generate_invite_token_shape():
    t = generate_invite_token()
    assert 8 <= len(t) <= 64
    assert " " not in t
