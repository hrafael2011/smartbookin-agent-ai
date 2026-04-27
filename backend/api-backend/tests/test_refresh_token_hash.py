from app.services.refresh_token_service import hash_refresh_plain


def test_hash_refresh_plain_stable():
    assert hash_refresh_plain("same-token") == hash_refresh_plain("same-token")
    assert hash_refresh_plain("a") != hash_refresh_plain("b")


def test_hash_strips_whitespace():
    assert hash_refresh_plain("  x  ") == hash_refresh_plain("x")
