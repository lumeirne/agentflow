"""Auth0 Token Vault client — the sole interface for OAuth token retrieval and management."""

import httpx
from backend.config import get_settings

settings = get_settings()

# Cache the management API token (short-lived, re-fetched when expired)
_mgmt_token_cache: dict | None = None


class TokenVaultClient:
    """
    Wraps Auth0 Management API v2 for Token Vault operations.

    IMPORTANT: Tokens retrieved by this client must NEVER be persisted
    to the application database or cached beyond a single API call scope.
    """

    def __init__(self):
        self.domain = settings.AUTH0_DOMAIN
        self.client_id = settings.AUTH0_CLIENT_ID
        self.client_secret = settings.AUTH0_CLIENT_SECRET
        self.audience = f"https://{self.domain}/api/v2/"
        self.base_url = f"https://{self.domain}/api/v2"

    async def get_management_token(self) -> str:
        """Obtain an Auth0 Management API access token (client credentials)."""
        global _mgmt_token_cache
        if _mgmt_token_cache is not None:
            return _mgmt_token_cache["access_token"]

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://{self.domain}/oauth/token",
                json={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "audience": self.audience,
                },
            )
            resp.raise_for_status()
            _mgmt_token_cache = resp.json()
        return _mgmt_token_cache["access_token"]

    async def get_user_token(self, user_id: str, connection: str) -> dict:
        """
        Retrieve user's OAuth token for a given connection from Token Vault.

        Returns: {"access_token": "...", "expires_in": ...}
        Token Vault handles refresh automatically.
        """
        mgmt_token = await self.get_management_token()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/users/{user_id}/tokens/{connection}",
                headers={"Authorization": f"Bearer {mgmt_token}"},
            )
            resp.raise_for_status()
        return resp.json()

    async def initiate_connection(self, user_id: str, connection: str, callback_url: str) -> str:
        """
        Start the OAuth connection flow via Token Vault.
        Returns the Auth0 authorization URL the user should be redirected to.
        """
        mgmt_token = await self.get_management_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/users/{user_id}/tokens",
                headers={"Authorization": f"Bearer {mgmt_token}"},
                json={
                    "connection": connection,
                    "callback_url": callback_url,
                },
            )
            resp.raise_for_status()
        data = resp.json()
        return data.get("authorization_url", data.get("redirect_url", ""))

    async def revoke_connection(self, user_id: str, connection: str) -> None:
        """Revoke and delete the token from Token Vault."""
        mgmt_token = await self.get_management_token()
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{self.base_url}/users/{user_id}/tokens/{connection}",
                headers={"Authorization": f"Bearer {mgmt_token}"},
            )
            resp.raise_for_status()

    async def list_connections(self, user_id: str) -> list[dict]:
        """List all federated identity tokens for a user."""
        mgmt_token = await self.get_management_token()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/users/{user_id}/tokens",
                headers={"Authorization": f"Bearer {mgmt_token}"},
            )
            resp.raise_for_status()
        return resp.json()


# Singleton
token_vault_client = TokenVaultClient()
