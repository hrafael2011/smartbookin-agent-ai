from datetime import timedelta

import jwt
import pytest

from app.core import security


def test_access_token_contains_kind_and_email():
    token = security.create_access_token(
        {"email": "u@example.com", "sub": "1"},
        expires_delta=timedelta(minutes=5),
        token_kind="access",
    )
    payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
    assert payload["email"] == "u@example.com"
    assert payload["token_kind"] == "access"
    assert "exp" in payload


def test_decode_token_rejects_garbage():
    with pytest.raises(jwt.PyJWTError):
        security.decode_token("not-a-jwt")
