from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi import HTTPException

from backend.middleware.auth import validate_bearer_token
from backend.tests.conftest import SAMPLE_MERCHANT_ID, make_expired_token, make_test_token


# ── validate_bearer_token ─────────────────────────────────────────────────────

def test_valid_token_returns_claims() -> None:
    token = make_test_token()
    claims = validate_bearer_token(token)
    assert claims["merchant_id"] == SAMPLE_MERCHANT_ID
    assert claims["email"] == "test@test.com"
    assert claims["role"] == "merchant"


def test_expired_token_raises_401() -> None:
    token = make_expired_token()
    with pytest.raises(HTTPException) as exc:
        validate_bearer_token(token)
    assert exc.value.status_code == 401
    assert "expired" in exc.value.detail.lower()


def test_empty_token_raises_401() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_bearer_token("   ")
    assert exc.value.status_code == 401


def test_malformed_token_raises_401() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_bearer_token("not.a.valid.jwt.at.all")
    assert exc.value.status_code == 401


def test_missing_merchant_id_raises_401() -> None:
    def _b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64(json.dumps({
        "email": "no-merchant@test.com",
        "exp": int(time.time()) + 3600,
    }).encode())
    sig = _b64(b"fakesig")
    token = f"{header}.{payload}.{sig}"

    with pytest.raises(HTTPException) as exc:
        validate_bearer_token(token)
    assert exc.value.status_code == 401


def test_missing_email_raises_401() -> None:
    def _b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64(json.dumps({
        "sub": SAMPLE_MERCHANT_ID,
        "merchant_id": SAMPLE_MERCHANT_ID,
        "exp": int(time.time()) + 3600,
    }).encode())
    sig = _b64(b"fakesig")
    token = f"{header}.{payload}.{sig}"

    with pytest.raises(HTTPException) as exc:
        validate_bearer_token(token)
    assert exc.value.status_code == 401


def test_role_defaults_to_merchant_when_missing() -> None:
    def _b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64(json.dumps({
        "sub": SAMPLE_MERCHANT_ID,
        "merchant_id": SAMPLE_MERCHANT_ID,
        "email": "test@test.com",
        "exp": int(time.time()) + 3600,
    }).encode())
    sig = _b64(b"fakesig")
    token = f"{header}.{payload}.{sig}"

    claims = validate_bearer_token(token)
    assert claims["role"] == "merchant"


def test_role_from_app_metadata() -> None:
    def _b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64(json.dumps({
        "sub": SAMPLE_MERCHANT_ID,
        "merchant_id": SAMPLE_MERCHANT_ID,
        "email": "admin@test.com",
        "app_metadata": {"role": "admin"},
        "exp": int(time.time()) + 3600,
    }).encode())
    sig = _b64(b"fakesig")
    token = f"{header}.{payload}.{sig}"

    claims = validate_bearer_token(token)
    assert claims["role"] == "admin"
