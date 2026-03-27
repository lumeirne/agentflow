"""GitHub API service — raw httpx calls to GitHub REST API."""

import httpx
from backend.auth.token_vault import (
    token_vault_client,
    ProviderConnectionMissingError,
    ProviderTokenExpiredError,
    ProviderTokenExchangeError,
    ProviderTemporaryError,
    ProviderError,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)


# Legacy alias kept for call-site compatibility during migration window
class TokenExpiredError(ProviderTokenExpiredError):
    """Legacy alias — prefer ProviderTokenExpiredError."""
    def __init__(self, message: str = ""):
        ProviderError.__init__(self, message or "GitHub token expired", provider="github", recoverable=True)


class GitHubService:
    """Low-level GitHub REST API wrapper. Token fetched per-call from Auth0 Token Vault."""

    BASE_URL = "https://api.github.com"

    async def _request(
        self,
        user_id: str,
        method: str,
        endpoint: str,
        db=None,
        auth0_user_id: str | None = None,
        **kwargs,
    ) -> dict | list:
        """Make an authenticated request to GitHub API."""
        logger.info(
            "Starting GitHub API request",
            extra={
                "data": {
                    "user_id": user_id,
                    "method": method,
                    "endpoint": endpoint,
                    "token_source": "auth0_token_vault",
                }
            },
        )
        # Token retrieved exclusively from Auth0 Token Vault
        token_data = await token_vault_client.get_user_token(
            user_id, "github", db=None, auth0_user_id=auth0_user_id
        )
        access_token = token_data["access_token"]

        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method,
                f"{self.BASE_URL}{endpoint}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                **kwargs,
            )

        logger.info(
            "GitHub API response received",
            extra={
                "data": {
                    "user_id": user_id,
                    "endpoint": endpoint,
                    "status_code": resp.status_code,
                    "token_source": "auth0_token_vault",
                }
            },
        )

        if resp.status_code in (401, 403):
            logger.warning(
                "GitHub authorization failed",
                extra={
                    "data": {
                        "user_id": user_id,
                        "endpoint": endpoint,
                        "status_code": resp.status_code,
                        "error_type": "ProviderTokenExpiredError",
                        "recoverable": True,
                        "token_source": "auth0_token_vault",
                    }
                },
            )
            raise ProviderTokenExpiredError("github")

        resp.raise_for_status()
        return resp.json()

    async def get_latest_pr(self, user_id: str, owner: str, repo: str, db=None, auth0_user_id: str | None = None) -> dict:
        """Fetch the latest open PR from a repository."""
        prs = await self._request(
            user_id, "GET",
            f"/repos/{owner}/{repo}/pulls",
            db=db,
            auth0_user_id=auth0_user_id,
            params={"state": "open", "sort": "created", "direction": "desc", "per_page": 1},
        )
        if not prs:
            raise ValueError(f"No open pull requests found in {owner}/{repo}")
        return prs[0]

    async def get_pr_details(self, user_id: str, owner: str, repo: str, pr_number: int, db=None, auth0_user_id: str | None = None) -> dict:
        """Fetch detailed info for a specific PR."""
        return await self._request(
            user_id, "GET", f"/repos/{owner}/{repo}/pulls/{pr_number}", db=db, auth0_user_id=auth0_user_id
        )

    async def get_pr_reviewers(self, user_id: str, owner: str, repo: str, pr_number: int, db=None, auth0_user_id: str | None = None) -> list[str]:
        """Get the list of requested reviewers for a PR."""
        data = await self._request(
            user_id, "GET",
            f"/repos/{owner}/{repo}/pulls/{pr_number}/requested_reviewers",
            db=db,
            auth0_user_id=auth0_user_id,
        )
        users = data.get("users", []) if isinstance(data, dict) else []
        return [u["login"] for u in users]

    async def get_repo_collaborators(self, user_id: str, owner: str, repo: str, db=None, auth0_user_id: str | None = None) -> list[str]:
        """Fallback: get repository collaborators when PR has no reviewers."""
        collabs = await self._request(
            user_id, "GET", f"/repos/{owner}/{repo}/collaborators", db=db, auth0_user_id=auth0_user_id
        )
        return [c["login"] for c in collabs]

    async def list_user_repos(self, user_id: str, db=None, auth0_user_id: str | None = None) -> list[dict]:
        """Fetch a list of repositories accessible to the authenticated user."""
        repos = await self._request(
            user_id, "GET",
            "/user/repos",
            db=db,
            auth0_user_id=auth0_user_id,
            params={"sort": "updated", "direction": "desc", "per_page": 100, "type": "all"},
        )
        logger.info(
            "Formatting GitHub repository list",
            extra={
                "data": {
                    "user_id": user_id,
                    "repo_count": len(repos),
                    "token_source": "auth0_token_vault",
                }
            },
        )
        return [
            {
                "name": r["name"],
                "full_name": r["full_name"],
                "description": r.get("description", ""),
                "url": r["html_url"],
                "updated_at": r["updated_at"],
            }
            for r in repos
        ]


# Singleton
github_service = GitHubService()
