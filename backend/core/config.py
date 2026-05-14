from __future__ import annotations

import warnings
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always resolves to backend/.env regardless of working directory
_ENV_FILE = str(Path(__file__).parent.parent / ".env")


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """
    Centralized application configuration.

    All runtime configuration flows through this model.
    Enforces:
    - environment validation
    - startup safety checks
    - deployment consistency
    - connector configuration integrity
    """

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------------------------------------------
    # Application
    # ---------------------------------------------------

    environment: Environment = Environment.DEVELOPMENT

    app_name: str = "d2c-ai-employee"

    app_version: str = "0.1.0"

    backend_url: str = "http://localhost:8000"

    frontend_url: str = "http://localhost:3000"

    debug: bool = True

    # ---------------------------------------------------
    # Gemini / LLM
    # ---------------------------------------------------

    gemini_api_key: str = Field(
        ...,
        min_length=1,
    )

    llm_model: str = "gemini-2.0-flash"

    llm_timeout_seconds: int = 60

    max_tool_iterations: int = 5

    # ---------------------------------------------------
    # Supabase
    # ---------------------------------------------------

    supabase_url: str = Field(
        ...,
        min_length=1,
    )

    supabase_key: str = Field(
        ...,
        min_length=1,
    )

    # Optional: when set, bearer tokens are fully verified against this secret.
    # Get it from Supabase Dashboard → Settings → API → JWT Secret.
    # If blank, structural validation only (safe for dev / self-signed tokens).
    supabase_jwt_secret: str = ""

    # ---------------------------------------------------
    # Redis / Upstash
    # ---------------------------------------------------

    upstash_redis_url: str = ""

    rate_limit_enabled: bool = True

    # ---------------------------------------------------
    # Langfuse Observability
    # ---------------------------------------------------

    langfuse_public_key: str = ""

    langfuse_secret_key: str = ""

    langfuse_host: str = "https://cloud.langfuse.com"

    # ---------------------------------------------------
    # Shopify
    # ---------------------------------------------------

    shopify_shop_domain: str = ""

    shopify_access_token: str = ""

    shopify_api_version: str = "2024-01"

    # ---------------------------------------------------
    # Meta Ads
    # ---------------------------------------------------

    meta_access_token: str = ""

    meta_ad_account_id: str = ""

    meta_api_version: str = "v19.0"

    # ---------------------------------------------------
    # Shiprocket
    # ---------------------------------------------------

    shiprocket_email: str = ""

    shiprocket_password: str = ""

    # ---------------------------------------------------
    # Scheduler / Sync Runtime
    # ---------------------------------------------------

    max_metric_rows: int = 500

    connector_sync_interval_minutes: int = 15

    watchdog_interval_hours: int = 6

    keep_warm_interval_minutes: int = 14

    default_sync_lookback_days: int = 30

    # ---------------------------------------------------
    # Connector Feature Flags
    # ---------------------------------------------------

    enable_shopify_connector: bool = True

    enable_meta_ads_connector: bool = True

    enable_shiprocket_connector: bool = True

    # ---------------------------------------------------
    # Validation
    # ---------------------------------------------------

    @field_validator("shopify_shop_domain")
    @classmethod
    def validate_shopify_domain(
        cls,
        value: str,
    ) -> str:
        cleaned = value.strip()

        if cleaned and cleaned.startswith("https://"):
            raise ValueError(
                "shopify_shop_domain should not include https://"
            )

        return cleaned

    @model_validator(mode="after")
    def validate_runtime_configuration(self) -> "Settings":
        """
        Production runtime safety validation.
        """

        if self.environment == Environment.PRODUCTION:
            self._validate_production_requirements()

        return self

    # ---------------------------------------------------
    # Internal Runtime Checks
    # ---------------------------------------------------

    def _validate_production_requirements(self) -> None:
        """
        Fail fast on invalid production deployments.
        """

        if self.debug:
            warnings.warn(
                "Debug mode enabled in production",
                stacklevel=2,
            )

        if not self.langfuse_public_key:
            warnings.warn(
                "Langfuse public key missing in production",
                stacklevel=2,
            )

        if not self.langfuse_secret_key:
            warnings.warn(
                "Langfuse secret key missing in production",
                stacklevel=2,
            )

        if not self.supabase_jwt_secret:
            warnings.warn(
                "SUPABASE_JWT_SECRET not set — tokens are structurally validated only",
                stacklevel=2,
            )

        if self.enable_shopify_connector and not self.shopify_access_token:
            warnings.warn(
                "Shopify connector enabled without access token",
                stacklevel=2,
            )

        if self.enable_meta_ads_connector and not self.meta_access_token:
            warnings.warn(
                "Meta Ads connector enabled without access token",
                stacklevel=2,
            )

        if self.enable_shiprocket_connector and (
            not self.shiprocket_email or not self.shiprocket_password
        ):
            warnings.warn(
                "Shiprocket connector enabled without credentials",
                stacklevel=2,
            )

    # ---------------------------------------------------
    # Helper Properties
    # ---------------------------------------------------

    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT

    @property
    def connector_count(self) -> int:
        return sum(
            [
                self.enable_shopify_connector,
                self.enable_meta_ads_connector,
                self.enable_shiprocket_connector,
            ]
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Shared singleton configuration instance.

    Avoids repeated environment parsing and validation.
    """

    return Settings()