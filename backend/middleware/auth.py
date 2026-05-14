from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

import jwt as pyjwt
from fastapi import HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.responses import Response

from backend.core.config import get_settings
from backend.core.logging import bind_merchant_id, bind_request_id, clear_runtime_context, get_logger


logger = get_logger(__name__)

_PUBLIC_PATH_PREFIXES = (
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
)


class AuthenticatedMerchant(BaseModel):
    """Authenticated tenant identity extracted from a validated bearer token."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    merchant_id: str = Field(..., min_length=1)
    email: str = Field(..., min_length=1)
    role: str = Field(default="merchant", min_length=1)

    @field_validator("merchant_id", "email", "role")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        """Strip surrounding whitespace and reject blank values."""

        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value cannot be empty")
        return cleaned


def _is_public_path(request: Request) -> bool:
    """Return True when the request should bypass tenant authentication."""

    path = request.url.path.rstrip("/") or "/"
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in _PUBLIC_PATH_PREFIXES)


def _request_id_from_headers(request: Request) -> str:
    """Extract or generate a stable request identifier for tracing."""

    request_id = request.headers.get("X-Request-Id") or request.headers.get("X-Request-ID")
    cleaned_request_id = (request_id or "").strip()
    if cleaned_request_id:
        return cleaned_request_id

    return f"req_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"


def _extract_claims(payload: dict[str, Any]) -> dict[str, Any]:
    """Pull merchant identity out of a decoded JWT payload."""
    merchant_id = payload.get("merchant_id") or payload.get("sub")
    email = payload.get("email") or payload.get("user_email") or payload.get("preferred_username")
    app_metadata = payload.get("app_metadata")
    role = payload.get("role")
    if isinstance(app_metadata, dict) and not role:
        role = app_metadata.get("role")

    if not isinstance(merchant_id, str) or not merchant_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization token",
        )
    if not isinstance(email, str) or not email.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization token",
        )

    normalized_role = role if isinstance(role, str) and role.strip() else "merchant"
    return {
        "merchant_id": merchant_id.strip(),
        "email": email.strip(),
        "role": normalized_role.strip(),
    }


def validate_bearer_token(token: str) -> dict[str, Any]:
    """Validate a bearer token and return trusted identity claims.

    When SUPABASE_JWT_SECRET is configured the signature is fully verified
    using HS256. Otherwise structural validation is performed (safe for dev
    and self-signed tokens from make_token.py).
    """
    cleaned_token = token.strip()
    if not cleaned_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization token",
        )

    settings = get_settings()

    if settings.supabase_jwt_secret:
        try:
            payload = pyjwt.decode(
                cleaned_token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                options={"verify_exp": True},
            )
        except pyjwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
            ) from None
        except pyjwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization token",
            ) from None
        return _extract_claims(payload)

    # ── Structural validation (no secret configured) ──────────────────────────
    parts = cleaned_token.split(".")
    if len(parts) != 3:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization token",
        )

    try:
        segment = parts[1]
        segment += "=" * ((-len(segment)) % 4)
        payload = json.loads(base64.urlsafe_b64decode(segment.encode("utf-8")).decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization token",
        ) from None

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization token",
        )

    exp_value = payload.get("exp")
    if exp_value is not None:
        try:
            expires_at = datetime.fromtimestamp(int(exp_value), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization token",
            ) from None
        if expires_at <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
            )

    return _extract_claims(payload)


async def get_authenticated_merchant(request: Request) -> AuthenticatedMerchant:
    """Validate request authentication headers and return the authenticated identity."""

    cached_merchant = getattr(request.state, "authenticated_merchant", None)
    if isinstance(cached_merchant, AuthenticatedMerchant):
        return cached_merchant

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        logger.warning(
            "auth_missing",
            auth_status="missing_authorization_header",
            request_id=getattr(request.state, "request_id", None),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        logger.warning(
            "auth_invalid",
            auth_status="malformed_authorization_header",
            request_id=getattr(request.state, "request_id", None),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header",
        )

    payload = validate_bearer_token(token)
    merchant = AuthenticatedMerchant(
        merchant_id=payload["merchant_id"],
        email=payload["email"],
        role=payload.get("role", "merchant"),
    )

    request.state.authenticated_merchant = merchant
    return merchant


async def get_merchant_id(request: Request) -> str:
    """Return the authenticated merchant identifier for the current request."""

    merchant = await get_authenticated_merchant(request)
    return merchant.merchant_id


async def auth_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Bind request identity context and reject unauthorized tenant access safely."""

    request_id = _request_id_from_headers(request)
    request.state.request_id = request_id
    bind_request_id(request_id)

    log = logger.bind(request_id=request_id, auth_status="pending")

    try:
        # OPTIONS requests are CORS preflight — browsers never send auth headers
        # on preflight. Let them pass so CORS middleware can respond correctly.
        if request.method == "OPTIONS" or _is_public_path(request):
            log.info("auth_skipped", path=request.url.path)
            response = await call_next(request)
            response.headers["X-Request-Id"] = request_id
            return response

        merchant = await get_authenticated_merchant(request)
        request.state.authenticated_merchant = merchant
        bind_merchant_id(merchant.merchant_id)

        log = log.bind(merchant_id=merchant.merchant_id, auth_status="authenticated")
        log.info("auth_success", path=request.url.path)

        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Merchant-Id"] = merchant.merchant_id
        return response

    except HTTPException as exc:
        log.warning(
            "auth_rejected",
            auth_status="rejected",
            status_code=exc.status_code,
            path=request.url.path,
        )
        raise

    except Exception:
        log.exception(
            "auth_failed",
            auth_status="error",
            path=request.url.path,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        ) from None

    finally:
        clear_runtime_context()