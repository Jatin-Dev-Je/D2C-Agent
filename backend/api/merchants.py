from __future__ import annotations

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from backend.core.database import get_merchant, register_merchant
from backend.middleware.auth import get_authenticated_merchant, get_merchant_id
from backend.middleware.rate_limit import check_rate_limit

router = APIRouter(prefix="/merchants", tags=["merchants"])
logger = structlog.get_logger(__name__)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    merchant=Depends(get_authenticated_merchant),
) -> dict:
    """Register or refresh the authenticated merchant in the merchants table.

    Safe to call on every login — uses upsert so duplicate calls are harmless.
    """
    row = await register_merchant(
        merchant_id=merchant.merchant_id,
        email=merchant.email,
        role=merchant.role,
    )
    logger.info(
        "merchant_register_api",
        merchant_id=merchant.merchant_id,
    )
    return {
        "merchant_id": row.get("merchant_id", merchant.merchant_id),
        "email": row.get("email", merchant.email),
        "role": row.get("role", merchant.role),
        "registered_at": row.get("created_at", datetime.now(timezone.utc).isoformat()),
    }


@router.get("/me")
async def me(
    merchant_id: str = Depends(get_merchant_id),
) -> dict:
    """Return the current merchant's profile from the merchants table."""
    await check_rate_limit(merchant_id)

    row = await get_merchant(merchant_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merchant not registered. Call POST /merchants/register first.",
        )
    return {
        "merchant_id": row["merchant_id"],
        "email": row["email"],
        "role": row["role"],
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }
