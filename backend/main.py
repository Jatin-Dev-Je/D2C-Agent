from __future__ import annotations

from datetime import datetime, timezone

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.agents import router as agents_router
from backend.api.connectors import router as connectors_router
from backend.api.dashboard import router as dashboard_router
from backend.api.merchants import router as merchants_router
from backend.api.metrics import router as metrics_router
from backend.chat.citation import CitationError
from backend.chat.router import router as chat_router
from backend.core.config import get_settings
from backend.core.logging import configure_logging
from backend.middleware.auth import auth_middleware
from backend.core.scheduler import lifespan


settings = get_settings()
configure_logging()
logger = structlog.get_logger(__name__)

app = FastAPI(
    title="D2C AI Employee",
    description="AI employees for D2C brands — cross-tool intelligence layer",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    swagger_ui_init_oauth={},
)


def _custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema.setdefault("components", {})["securitySchemes"] = {
        "BearerAuth": {"type": "http", "scheme": "bearer"}
    }
    schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = schema
    return schema


app.openapi = _custom_openapi

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.environment == "development" else [settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(auth_middleware)

app.include_router(chat_router)
app.include_router(agents_router)
app.include_router(metrics_router)
app.include_router(connectors_router)
app.include_router(dashboard_router)
app.include_router(merchants_router)


@app.exception_handler(CitationError)
async def citation_error_handler(request: Request, exc: CitationError) -> JSONResponse:
    logger.warning("citation_error_response", error=str(exc))
    return JSONResponse(
        status_code=422,
        content={"error": str(exc), "type": "citation_error"},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    from fastapi import HTTPException as _HTTPException
    if isinstance(exc, _HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    logger.error("unhandled_exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "type": "internal_error"},
    )


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {
        "status": "ok",
        "env": settings.environment,
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/", tags=["system"])
async def root() -> dict:
    return {
        "message": "D2C AI Employee API",
        "docs_url": "/docs",
        "routes": ["/chat", "/agents", "/metrics", "/connectors", "/dashboard"],
    }
