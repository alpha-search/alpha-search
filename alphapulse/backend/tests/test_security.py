"""Unit tests for JWT issuance/verification and password hashing."""
from __future__ import annotations

import time

import jwt
import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_round_trip() -> None:
    hashed = hash_password("s3cret-password")
    assert hashed != "s3cret-password"
    assert verify_password("s3cret-password", hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_round_trip() -> None:
    token = create_access_token("user-123", extra_claims={"role": "contributor"})
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == "user-123"
    assert payload["role"] == "contributor"
    assert payload["type"] == "access"


def test_refresh_token_rejected_on_access_route() -> None:
    refresh = create_refresh_token("user-123")
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(refresh, expected_type="access")


def test_tampered_token_rejected() -> None:
    token = create_access_token("user-123")
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token + "tamper", expected_type="access")


def test_expired_token_rejected() -> None:
    # Issue a token that is already expired by hand-crafting the exp claim.
    from app.core.config import settings

    payload = {
        "sub": "user-123",
        "type": "access",
        "exp": int(time.time()) - 10,
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token, expected_type="access")
