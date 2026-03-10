"""
Authentication dependency for extracting user from Supabase JWT.
"""

import logging
from typing import Optional
from fastapi import Header, HTTPException
from ..db.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


async def get_current_user_id(authorization: Optional[str] = Header(None)) -> str:
    """
    Extract user ID from the Supabase access token.
    Raises 401 if no valid token is provided.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        client = get_supabase_client()
        resp = client.auth.get_user(token)
        if resp and resp.user:
            return resp.user.id
    except Exception as e:
        logger.warning(f"JWT validation failed: {e}")

    raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_optional_user_id(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """
    Extract user ID if a valid token is provided; return None otherwise.
    Use for endpoints that work both authenticated and unauthenticated.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return None

    try:
        client = get_supabase_client()
        resp = client.auth.get_user(token)
        if resp and resp.user:
            return resp.user.id
    except Exception as e:
        logger.debug(f"JWT validation failed: {e}")

    return None
