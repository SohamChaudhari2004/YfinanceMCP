"""API-key check and rate limiting."""

import logging
import secrets

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, description="Your API key")

# Keyed by client IP. On Render, uvicorn runs with --proxy-headers so this is the real
# client IP from X-Forwarded-For, not the load balancer's.
limiter = Limiter(key_func=get_remote_address, headers_enabled=True)

if not settings.api_keys:
    logger.warning("API_KEYS is not set: API-key check is DISABLED. Set it in production.")


def require_api_key(api_key: str | None = Security(api_key_header)) -> None:
    if not settings.api_keys:
        return
    if api_key and any(secrets.compare_digest(api_key, valid) for valid in settings.api_keys):
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid X-API-Key header.",
    )
