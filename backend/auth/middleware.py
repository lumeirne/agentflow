"""Auth0 JWT verification middleware."""

from typing import Optional

import httpx
from fastapi import Depends, HTTPException, Request, status
from jose import jwt, JWTError

from backend.config import get_settings
from backend.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

# Cache JWKS keys in memory
_jwks_cache: Optional[dict] = None


async def _get_jwks() -> dict:
    """Fetch the Auth0 JWKS key set (cached after first call)."""
    global _jwks_cache
    if _jwks_cache is not None:
        logger.info("Using cached JWKS")
        return _jwks_cache

    jwks_url = f"https://{settings.AUTH0_DOMAIN}/.well-known/jwks.json"
    logger.info("Fetching JWKS from Auth0", extra={"data": {"jwks_url": jwks_url}})
    async with httpx.AsyncClient() as client:
        resp = await client.get(jwks_url)
        resp.raise_for_status()
        _jwks_cache = resp.json()
    logger.info("JWKS fetched and cached")
    return _jwks_cache


def _get_token_from_header(request: Request) -> str:
    """Extract the Bearer token from the Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        logger.warning("Missing or invalid Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    return auth_header[7:]


async def verify_jwt(request: Request) -> dict:
    """
    FastAPI dependency that verifies an Auth0 JWT.

    Returns the decoded token payload on success.
    Raises 401 on any failure (missing, expired, invalid).
    """
    token = _get_token_from_header(request)
    logger.info("Verifying JWT")

    try:
        jwks = await _get_jwks()
        unverified_header = jwt.get_unverified_header(token)

        # Find the matching key
        rsa_key = {}
        for key in jwks.get("keys", []):
            if key["kid"] == unverified_header.get("kid"):
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
                break

        if not rsa_key:
            logger.warning("No matching signing key found", extra={"data": {"kid": unverified_header.get("kid")}})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find appropriate signing key",
            )

        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=settings.AUTH0_AUDIENCE,
            issuer=f"https://{settings.AUTH0_DOMAIN}/",
        )
        logger.info("JWT verification succeeded", extra={"data": {"sub": payload.get("sub")}})
        return payload

    except JWTError as e:
        logger.warning("JWT verification failed", extra={"data": {"error": str(e)}})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {str(e)}",
        )
    except httpx.HTTPError:
        logger.error("Auth0 unreachable during JWT verification")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to verify token — Auth0 unreachable",
        )
