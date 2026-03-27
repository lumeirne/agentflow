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
    return id_provider in accepted or id_connection in accepted


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
                identities = user_resp.json().get("identities", [])
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

                for identity in identities:
                    if not _identity_matches_provider(identity, connection):
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
