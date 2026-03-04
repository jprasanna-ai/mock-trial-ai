"""
Authentication dependency for extracting user from Supabase JWT.
"""

import logging
from typing import Optional
from fastapi import Header
from ..db.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


async def get_current_user_id(authorization: Optional[str] = Header(None)) -> str:
    """
    Extract user ID from the Supabase access token.
    Falls back to 'default' for backward compatibility when no token is provided.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return "default"

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return "default"

    try:
        client = get_supabase_client()
        resp = client.auth.get_user(token)
        if resp and resp.user:
            return resp.user.id
    except Exception as e:
        logger.debug(f"JWT validation failed: {e}")

    return "default"
