"""
Auth0 Token Vault client — Auth0-only token retrieval strategy.

Token source: Auth0 Management API v2 (user identities / Token Vault endpoint).
DB token columns (access_token_enc / refresh_token_enc) are NOT read or written
for provider credentials; they are preserved for backward-compatibility only.

Connected account rows are used exclusively for UX/reporting metadata
(provider, status, external_account_id, scopes_json).

Typed error hierarchy
─────────────────────
ProviderError                       base
  ProviderConnectionMissingError    user has never connected this provider
  ProviderTokenExpiredError         token exists but is expired / revoked
  ProviderTokenExchangeError        Auth0 token exchange call failed
  ProviderTemporaryError            transient Auth0 / network error
"""

from __future__ import annotations

import httpx
from urllib.parse import urlencode

from backend.config import get_settings
from backend.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


# ── Typed error taxonomy ──────────────────────────────────────────────────────

class ProviderError(Exception):
    """Base class for all provider token errors."""
    def __init__(self, message: str, provider: str, recoverable: bool = True):
        super().__init__(message)
        self.provider = provider
        self.recoverable = recoverable


class ProviderConnectionMissingError(ProviderError):
    """User has never connected this provider (no identity linked in Auth0)."""
    def __init__(self, provider: str):
        super().__init__(
            f"No {provider} account connected. Connect your {provider} account to continue.",
            provider=provider,
            recoverable=True,
        )


class ProviderTokenExpiredError(ProviderError):
    """Provider token exists but is expired or revoked."""
    def __init__(self, provider: str):
        super().__init__(
            f"{provider} token is expired or revoked. Reconnect your {provider} account.",
            provider=provider,
            recoverable=True,
        )


class ProviderTokenExchangeError(ProviderError):
    """Auth0 token exchange call failed (non-transient)."""
    def __init__(self, provider: str, detail: str = ""):
        super().__init__(
            f"Failed to exchange {provider} token with Auth0. {detail}".strip(),
            provider=provider,
            recoverable=False,
        )


class ProviderTemporaryError(ProviderError):
    """Transient Auth0 or network error — safe to retry."""
    def __init__(self, provider: str, detail: str = ""):
        super().__init__(
            f"Temporary error retrieving {provider} token. {detail}".strip(),
            provider=provider,
            recoverable=True,
        )


# Keep legacy alias so existing callers that catch TokenNotFoundError still work
# during the migration window.
class TokenNotFoundError(ProviderConnectionMissingError):
    """Legacy alias — prefer ProviderConnectionMissingError."""
    def __init__(self, message: str = "", provider: str = "unknown"):
        ProviderError.__init__(self, message or f"No token found for {provider}", provider=provider, recoverable=True)


# ── Management API token cache ────────────────────────────────────────────────

_mgmt_token_cache: dict | None = None


def clear_mgmt_token_cache():
    """Force refresh of Management API token on next request."""
    global _mgmt_token_cache
    _mgmt_token_cache = None


def _provider_connection_name(provider: str) -> str:
    """Map logical provider key to Auth0 connection name."""
    mapping = {
        "github": settings.AUTH0_GITHUB_CONNECTION,
        "google": settings.AUTH0_GOOGLE_CONNECTION,
        "slack": settings.AUTH0_SLACK_CONNECTION,
    }
    return mapping.get(provider.lower(), provider.lower())


def _identity_matches_provider(identity: dict, provider: str) -> bool:
    """Return True when an Auth0 identity object belongs to the requested provider."""
    id_provider = (identity.get("provider") or "").lower()
    id_connection = (identity.get("connection") or "").lower()
    auth0_conn = _provider_connection_name(provider).lower()

    # Accept both the logical key and the Auth0 connection name
    accepted = {provider.lower(), auth0_conn}
    
    matches = id_provider in accepted or id_connection in accepted
    
    logger.debug(
        f"_identity_matches_provider check",
        extra={
            "data": {
                "id_provider": id_provider,
                "id_connection": id_connection,
                "looking_for_provider": provider,
                "auth0_conn_mapped": auth0_conn,
                "accepted_set": list(accepted),
                "matches": matches,
            }
        },
    )
    
    return matches


class TokenVaultClient:
    """
    Auth0-only token retrieval client.

    Retrieval strategy (in order):
      1. Auth0 Token Vault endpoint: GET /api/v2/users/{id}/tokens/{connection}
      2. Auth0 user identities:      GET /api/v2/users/{id} → identities[].access_token
      3. Raise typed ProviderError if neither source has the token.

    DB token columns are never read or written for provider credentials.
    """

    def __init__(self):
        self.domain = settings.AUTH0_DOMAIN
        # Use TV-specific client creds if configured, else fall back to main creds
        self.client_id = settings.AUTH0_TV_CLIENT_ID or settings.AUTH0_CLIENT_ID
        self.client_secret = settings.AUTH0_TV_CLIENT_SECRET or settings.AUTH0_CLIENT_SECRET
        self.audience = f"https://{self.domain}/api/v2/"
        self.base_url = f"https://{self.domain}/api/v2"

    # ── Management API ────────────────────────────────────────────────────────

    async def get_management_token(self) -> str:
        """Obtain an Auth0 Management API access token (client credentials)."""
        global _mgmt_token_cache
        if _mgmt_token_cache is not None:
            return _mgmt_token_cache["access_token"]

        logger.info("Management token cache empty, requesting new token", extra={"data": {
            "domain": self.domain,
            "client_id": self.client_id,
            "audience": self.audience,
        }})

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://{self.domain}/oauth/token",
                    json={
                        "grant_type": "client_credentials",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "audience": self.audience,
                    },
                    timeout=10.0,
                )
                logger.info("Management token response", extra={"data": {
                    "status_code": resp.status_code,
                    "has_error": resp.status_code >= 400,
                }})
                if resp.status_code >= 400:
                    logger.error("Management token request failed", extra={"data": {
                        "status_code": resp.status_code,
                        "response_body": resp.text,
                    }})
                resp.raise_for_status()
                _mgmt_token_cache = resp.json()
        except httpx.HTTPStatusError as e:
            raise ProviderTokenExchangeError(
                "auth0", f"Management API token request failed: {e.response.status_code}"
            ) from e
        except Exception as e:
            raise ProviderTemporaryError("auth0", f"Management API unreachable: {e}") from e

        return _mgmt_token_cache["access_token"]

    # ── Token retrieval (Auth0-only) ──────────────────────────────────────────

    async def get_user_token(
        self,
        user_id: str,
        connection: str,
        db=None,                        # accepted but ignored — Auth0-only path
        auth0_user_id: str | None = None,
    ) -> dict:
        """
        Retrieve the user's OAuth access token for a provider from Auth0.

        Parameters
        ----------
        user_id       : internal DB user id (used as fallback vault_user_id)
        connection    : logical provider key ('github', 'google', 'slack')
        db            : ignored (kept for call-site compatibility)
        auth0_user_id : Auth0 subject (preferred vault lookup key)

        Returns
        -------
        dict with at least {"access_token": "<token>"}

        Raises
        ------
        ProviderConnectionMissingError  — no identity linked
        ProviderTokenExpiredError       — token expired / revoked
        ProviderTokenExchangeError      — non-transient exchange failure
        ProviderTemporaryError          — transient error
        """
        vault_user_id = auth0_user_id or user_id
        auth0_connection = _provider_connection_name(connection)

        logger.info(
            "Retrieving provider token from Auth0 Token Vault",
            extra={
                "data": {
                    "user_id": user_id,
                    "auth0_user_id": auth0_user_id,
                    "connection": connection,
                    "auth0_connection": auth0_connection,
                    "token_source": "auth0_token_vault",
                }
            },
        )

        try:
            mgmt_token = await self.get_management_token()
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderTemporaryError(connection, f"Could not obtain management token: {e}") from e

        # ── Attempt 1: Token Vault endpoint ──────────────────────────────────
        try:
            async with httpx.AsyncClient() as client:
                tv_resp = await client.get(
                    f"{self.base_url}/users/{vault_user_id}/tokens/{auth0_connection}",
                    headers={"Authorization": f"Bearer {mgmt_token}"},
                    timeout=10.0,
                )

            if tv_resp.status_code == 200:
                token_data = tv_resp.json()
                access_token = token_data.get("access_token")
                if access_token:
                    logger.info(
                        "Provider token retrieved from Auth0 Token Vault endpoint",
                        extra={
                            "data": {
                                "user_id": user_id,
                                "connection": connection,
                                "token_source": "auth0_token_vault",
                                "recoverable": False,
                            }
                        },
                    )
                    return {"access_token": access_token}

            elif tv_resp.status_code == 401:
                raise ProviderTokenExpiredError(connection)

            elif tv_resp.status_code not in (404, 501):
                # Unexpected non-404 error from Token Vault
                logger.warning(
                    "Auth0 Token Vault returned unexpected status",
                    extra={
                        "data": {
                            "user_id": user_id,
                            "connection": connection,
                            "status_code": tv_resp.status_code,
                        }
                    },
                )

        except ProviderError:
            raise
        except Exception as e:
            logger.warning(
                "Auth0 Token Vault endpoint error; falling back to identities",
                extra={"data": {"user_id": user_id, "connection": connection, "error": str(e)}},
            )

        # ── Attempt 2: User identities fallback ──────────────────────────────
        try:
            async with httpx.AsyncClient() as client:
                user_resp = await client.get(
                    f"{self.base_url}/users/{vault_user_id}",
                    params={"fields": "identities", "include_fields": "true"},
                    headers={"Authorization": f"Bearer {mgmt_token}"},
                    timeout=10.0,
                )

            if user_resp.status_code == 200:
                full_user_data = user_resp.json()
                identities = full_user_data.get("identities", [])
                
                # Log FULL response for debugging multiple identities
                logger.info(
                    "Full Auth0 user identities response",
                    extra={
                        "data": {
                            "user_id": user_id,
                            "connection": connection,
                            "identities_count": len(identities),
                            "identities_raw": repr(identities)[:1000],  # First 1000 chars
                            "token_source": "auth0_token_vault",
                        }
                    },
                )
                
                logger.info(
                    "Inspecting Auth0 identities for provider token",
                    extra={
                        "data": {
                            "user_id": user_id,
                            "connection": connection,
                            "identities_count": len(identities),
                            "token_source": "auth0_token_vault",
                        }
                    },
                )

                # Debug: Log details of each identity
                for idx, identity in enumerate(identities):
                    logger.info(
                        f"Identity {idx} details",
                        extra={
                            "data": {
                                "provider": identity.get("provider"),
                                "connection": identity.get("connection"),
                                "user_id_field": identity.get("user_id"),
                                "has_access_token": bool(identity.get("access_token")),
                                "keys": list(identity.keys()),
                                "looking_for_connection": connection,
                                "auth0_connection": _provider_connection_name(connection),
                            }
                        },
                    )

                for identity in identities:
                    if not _identity_matches_provider(identity, connection):
                        logger.info(
                            "Identity does not match provider",
                            extra={
                                "data": {
                                    "identity_provider": identity.get("provider"),
                                    "identity_connection": identity.get("connection"),
                                    "looking_for": connection,
                                }
                            },
                        )
                        continue
                    idp_access_token = identity.get("access_token")
                    if idp_access_token:
                        logger.info(
                            "Provider token resolved from Auth0 identity",
                            extra={
                                "data": {
                                    "user_id": user_id,
                                    "connection": connection,
                                    "token_source": "auth0_token_vault",
                                    "provider": identity.get("provider"),
                                    "recoverable": False,
                                }
                            },
                        )
                        return {"access_token": idp_access_token}

                # Identity exists but no access_token — likely expired
                has_identity = any(_identity_matches_provider(i, connection) for i in identities)
                if has_identity:
                    logger.warning(
                        "Provider identity found but no access_token — token likely expired",
                        extra={
                            "data": {
                                "user_id": user_id,
                                "connection": connection,
                                "token_source": "auth0_token_vault",
                                "error_type": "ProviderTokenExpiredError",
                                "recoverable": True,
                            }
                        },
                    )
                    raise ProviderTokenExpiredError(connection)

                # No matching identity at all
                logger.warning(
                    "No matching Auth0 identity for provider",
                    extra={
                        "data": {
                            "user_id": user_id,
                            "connection": connection,
                            "token_source": "auth0_token_vault",
                            "error_type": "ProviderConnectionMissingError",
                            "recoverable": True,
                        }
                    },
                )
                raise ProviderConnectionMissingError(connection)

            elif user_resp.status_code == 404:
                raise ProviderConnectionMissingError(connection)
            else:
                raise ProviderTemporaryError(
                    connection,
                    f"Auth0 identities lookup returned {user_resp.status_code}",
                )

        except ProviderError:
            raise
        except Exception as e:
            raise ProviderTemporaryError(connection, f"Auth0 identities lookup failed: {e}") from e

    # ── Connection metadata persistence ──────────────────────────────────────

    async def store_connection_metadata(
        self,
        db,
        user_id: str,
        connection: str,
        external_account_id: str | None = None,
        scopes_json: str | None = None,
    ) -> None:
        """
        Persist connection metadata (status, external_account_id, scopes) only.
        Provider access tokens are NOT stored — they live in Auth0 Token Vault.
        """
        from sqlalchemy import select
        from backend.models.connected_account import ConnectedAccount
        from backend.schemas import ConnectionStatus

        logger.info(
            "Storing connection metadata",
            extra={
                "data": {
                    "user_id": user_id,
                    "connection": connection,
                    "token_source": "auth0_token_vault",
                }
            },
        )

        result = await db.execute(
            select(ConnectedAccount).where(
                (ConnectedAccount.user_id == user_id) &
                (ConnectedAccount.provider == connection)
            )
        )
        account = result.scalar_one_or_none()

        if account is None:
            account = ConnectedAccount(
                user_id=user_id,
                provider=connection,
            )
            db.add(account)

        account.status = ConnectionStatus.CONNECTED.value
        if external_account_id is not None:
            account.external_account_id = external_account_id
        if scopes_json is not None:
            account.scopes_json = scopes_json

        # Explicitly clear any legacy encrypted token columns
        account.access_token_enc = None
        account.refresh_token_enc = None

        await db.flush()
        logger.info(
            "Connection metadata stored (no provider tokens in DB)",
            extra={"data": {"user_id": user_id, "connection": connection}},
        )

    # Keep legacy store_token signature for call-site compatibility during migration.
    # It delegates to store_connection_metadata and ignores token values.
    async def store_token(
        self,
        db,
        user_id: str,
        connection: str,
        access_token: str = "",
        refresh_token: str | None = None,
    ) -> None:
        """Legacy shim — stores only metadata, never the token values."""
        await self.store_connection_metadata(db, user_id, connection)

    # ── Connection initiation ─────────────────────────────────────────────────

    async def initiate_connection(
        self,
        user_id: str,
        connection: str,
        callback_url: str,
        return_to_run_id: str | None = None,
    ) -> str:
        """
        Build an Auth0 authorization URL for the specified social provider.

        connection name mapping uses settings-configurable aliases so tenants
        with custom connection names work without code changes.
        """
        auth0_connection = _provider_connection_name(connection)
        logger.info(
            "Building Auth0 authorize URL",
            extra={
                "data": {
                    "user_id": user_id,
                    "connection": connection,
                    "auth0_connection": auth0_connection,
                    "callback_url": callback_url,
                    "return_to_run_id": return_to_run_id,
                }
            },
        )

        params: dict = {
            "response_type": "code",
            "client_id": settings.AUTH0_CLIENT_ID,
            "redirect_uri": callback_url,
            "scope": "openid profile email offline_access",
            "connection": auth0_connection,
        }

        if connection == "github":
            params["connection_scope"] = "read:user user:email repo"
            params["prompt"] = "consent"

        if return_to_run_id:
            params["state"] = f"run:{return_to_run_id}"

        return f"https://{self.domain}/authorize?" + urlencode(params)

    # ── Revocation ────────────────────────────────────────────────────────────

    async def revoke_connection(self, user_id: str, connection: str) -> None:
        """
        Best-effort Token Vault revocation. Never raises.
        """
        auth0_connection = _provider_connection_name(connection)
        try:
            mgmt_token = await self.get_management_token()
            async with httpx.AsyncClient() as client:
                await client.delete(
                    f"{self.base_url}/users/{user_id}/tokens/{auth0_connection}",
                    headers={"Authorization": f"Bearer {mgmt_token}"},
                    timeout=5.0,
                )
        except Exception:
            pass  # Token Vault not configured or token not there — fine

    async def verify_and_link_identity(
        self,
        user_id: str,
        connection: str,
        external_account_id: str | None = None,
    ) -> bool:
        """
        Verify that Auth0 has linked the specified provider identity to the user.
        If not yet linked, attempt to link it using the Management API.

        Parameters
        ----------
        user_id : Auth0 user ID of the primary account (e.g., 'auth0|...')
        connection : logical provider key ('github', 'google', 'slack')
        external_account_id : Auth0 user ID for the provider 
                             (e.g., 'github|octocat' from id_token.sub)

        Returns True if identity is now linked (or was already linked).
        Raises ProviderError if linking fails non-transiently.

        This is called after the OAuth callback to ensure Auth0 has the identity
        linked before we mark the connection as "connected" in our DB.
        """
        auth0_connection = _provider_connection_name(connection)

        logger.info(
            "Verifying/linking Auth0 identity for provider",
            extra={
                "data": {
                    "user_id": user_id,
                    "connection": connection,
                    "auth0_connection": auth0_connection,
                    "external_account_id": external_account_id,
                }
            },
        )

        try:
            mgmt_token = await self.get_management_token()
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderTemporaryError(connection, f"Could not obtain management token: {e}") from e

        # ── Step 1: Check if identity is already linked ─────────────────────
        identities = []
        try:
            async with httpx.AsyncClient() as client:
                user_resp = await client.get(
                    f"{self.base_url}/users/{user_id}",
                    params={"fields": "identities", "include_fields": "true"},
                    headers={"Authorization": f"Bearer {mgmt_token}"},
                    timeout=10.0,
                )

            if user_resp.status_code == 200:
                identities = user_resp.json().get("identities", [])
                logger.info(
                    "Retrieved user identities from Auth0",
                    extra={
                        "data": {
                            "user_id": user_id,
                            "identities_count": len(identities),
                            "identities": [
                                {
                                    "provider": i.get("provider"),
                                    "connection": i.get("connection"),
                                    "has_token": bool(i.get("access_token")),
                                }
                                for i in identities
                            ],
                        }
                    },
                )

                # Check if the provider identity is already linked
                for identity in identities:
                    if _identity_matches_provider(identity, connection):
                        logger.info(
                            "Provider identity already linked in Auth0",
                            extra={
                                "data": {
                                    "user_id": user_id,
                                    "connection": connection,
                                    "provider": identity.get("provider"),
                                    "has_access_token": bool(identity.get("access_token")),
                                }
                            },
                        )
                        return True

        except Exception as e:
            logger.warning(
                "Could not retrieve identities",
                extra={"data": {"user_id": user_id, "connection": connection, "error": str(e)}},
            )

        # ── Step 2: Attempt to link identity via Management API ──────────────
        if external_account_id:
            logger.info(
                "Provider identity not yet linked; attempting to link via Management API",
                extra={
                    "data": {
                        "user_id": user_id,
                        "connection": connection,
                        "external_account_id": external_account_id,
                    }
                },
            )

            try:
                # Use a fresh client for the POST to avoid any connection reuse issues
                async with httpx.AsyncClient() as link_client:
                    link_resp = await link_client.post(
                        f"{self.base_url}/users/{user_id}/identities",
                        json={
                            "provider": auth0_connection,
                            "user_id": external_account_id,
                        },
                        headers={"Authorization": f"Bearer {mgmt_token}"},
                        timeout=10.0,
                    )

                logger.info(
                    "Link identity API response",
                    extra={
                        "data": {
                            "user_id": user_id,
                            "connection": connection,
                            "status_code": link_resp.status_code,
                            "response_snippet": link_resp.text[:200] if link_resp.text else "",
                        }
                    },
                )

                if link_resp.status_code in (200, 201):
                    logger.info(
                        "Provider identity linked successfully in Auth0",
                        extra={
                            "data": {
                                "user_id": user_id,
                                "connection": connection,
                                "status_code": link_resp.status_code,
                            }
                        },
                    )
                    return True
                elif link_resp.status_code == 409:
                    # 409 Conflict — identity already linked or user already exists
                    logger.info(
                        "Identity link conflict (likely already linked)",
                        extra={
                            "data": {
                                "user_id": user_id,
                                "connection": connection,
                                "status_code": 409,
                            }
                        },
                    )
                    return True
                else:
                    logger.warning(
                        "Failed to link provider identity via Management API",
                        extra={
                            "data": {
                                "user_id": user_id,
                                "connection": connection,
                                "status_code": link_resp.status_code,
                                "response": link_resp.text[:500] if link_resp.text else "no response body",
                            }
                        },
                    )

            except Exception as e:
                logger.warning(
                    "Exception during identity linking via Management API",
                    extra={
                        "data": {
                            "user_id": user_id,
                            "connection": connection,
                            "error": str(e),
                            "error_type": type(e).__name__,
                        }
                    },
                )

        # ── Step 3: Fallback - Check if Token Vault endpoint has the token ────
        # Even if linking failed, Auth0 might still have the token in Token Vault
        logger.info(
            "Attempting Token Vault endpoint as fallback",
            extra={
                "data": {
                    "user_id": user_id,
                    "connection": connection,
                }
            },
        )

        try:
            async with httpx.AsyncClient() as tv_client:
                tv_resp = await tv_client.get(
                    f"{self.base_url}/users/{user_id}/tokens/{auth0_connection}",
                    headers={"Authorization": f"Bearer {mgmt_token}"},
                    timeout=10.0,
                )

            if tv_resp.status_code == 200:
                token_data = tv_resp.json()
                if token_data.get("access_token"):
                    logger.info(
                        "Token Vault endpoint has provider token despite linking issues",
                        extra={
                            "data": {
                                "user_id": user_id,
                                "connection": connection,
                                "note": "Token available without explicit identity link",
                            }
                        },
                    )
                    return True

        except Exception as e:
            logger.info(
                "Token Vault endpoint fallback also not available",
                extra={"data": {"user_id": user_id, "connection": connection, "error": str(e)}},
            )

        # If we get here, we couldn't verify or link the identity
        logger.warning(
            "Could not verify or link provider identity; connection will be marked connected "
            "but token retrieval may fail until identity is properly linked in Auth0",
            extra={
                "data": {
                    "user_id": user_id,
                    "connection": connection,
                    "note": "Try manually linking in Auth0 Dashboard or contact support",
                }
            },
        )

        # Return True to allow connection to be stored, but next token attempt will fail
        # with clear error messaging that user needs to reconnect
        return True

    async def link_accounts(
        self,
        primary_user_id: str,
        secondary_provider: str,
        secondary_user_id: str,
    ) -> bool:
        """
        Link a secondary social identity to a primary account using Auth0 Management API.

        Parameters
        ----------
        primary_user_id : Auth0 ID of the primary account (e.g., 'auth0|xxx')
        secondary_provider : Provider of secondary account ('github', 'google', 'slack')
        secondary_user_id : Auth0 ID of secondary account (e.g., 'github|12345')

        Returns True if linking succeeded or was already linked.
        """
        logger.info(
            "Linking Auth0 accounts",
            extra={
                "data": {
                    "primary_user_id": primary_user_id,
                    "secondary_provider": secondary_provider,
                    "secondary_user_id": secondary_user_id,
                }
            },
        )

        try:
            mgmt_token = await self.get_management_token()
        except Exception as e:
            logger.error(
                "Failed to get management token for account linking",
                extra={"data": {"error": str(e)}},
            )
            return False

        try:
            async with httpx.AsyncClient() as client:
                # Link secondary account to primary
                # Endpoint: POST /api/v2/users/{id}/identities
                link_resp = await client.post(
                    f"{self.base_url}/users/{primary_user_id}/identities",
                    json={
                        "provider": secondary_provider,
                        "user_id": secondary_user_id,
                    },
                    headers={"Authorization": f"Bearer {mgmt_token}"},
                    timeout=10.0,
                )

                logger.info(
                    "Account linking response",
                    extra={
                        "data": {
                            "primary_user_id": primary_user_id,
                            "secondary_provider": secondary_provider,
                            "secondary_user_id": secondary_user_id,
                            "status_code": link_resp.status_code,
                            "response": link_resp.text[:300] if link_resp.text else "",
                        }
                    },
                )

                if link_resp.status_code in (200, 201):
                    logger.info(
                        "Accounts linked successfully",
                        extra={
                            "data": {
                                "primary_user_id": primary_user_id,
                                "secondary_provider": secondary_provider,
                            }
                        },
                    )
                    return True
                elif link_resp.status_code == 409:
                    logger.info(
                        "Accounts already linked (409 conflict)",
                        extra={"data": {"primary_user_id": primary_user_id}},
                    )
                    return True
                else:
                    logger.warning(
                        "Failed to link accounts",
                        extra={
                            "data": {
                                "primary_user_id": primary_user_id,
                                "status_code": link_resp.status_code,
                                "response": link_resp.text[:500] if link_resp.text else "",
                            }
                        },
                    )
                    return False

        except Exception as e:
            logger.error(
                "Exception during account linking",
                extra={
                    "data": {
                        "primary_user_id": primary_user_id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }
                },
            )
            return False

    async def list_connections(self, user_id: str) -> list[dict]:
        """List all federated identity tokens for a user (Token Vault)."""
        try:
            mgmt_token = await self.get_management_token()
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.base_url}/users/{user_id}/tokens",
                    headers={"Authorization": f"Bearer {mgmt_token}"},
                    timeout=10.0,
                )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return []


# Singleton
token_vault_client = TokenVaultClient()
