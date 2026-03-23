"""GitHub API service — raw httpx calls to GitHub REST API."""

import httpx
from backend.auth.token_vault import token_vault_client


class TokenExpiredError(Exception):
    """Raised when the GitHub token is expired or revoked (401/403)."""
    pass


class GitHubService:
    """Low-level GitHub REST API wrapper. Token fetched per-call from Token Vault."""

    BASE_URL = "https://api.github.com"

    async def _request(self, user_id: str, method: str, endpoint: str, **kwargs) -> dict | list:
        """Make an authenticated request to GitHub API."""
        token_data = await token_vault_client.get_user_token(user_id, "github")
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
            # Token goes out of scope after this block

        if resp.status_code in (401, 403):
            raise TokenExpiredError(
                f"GitHub authorization failed ({resp.status_code}). Please reconnect your GitHub account."
            )
        resp.raise_for_status()
        return resp.json()

    async def get_latest_pr(self, user_id: str, owner: str, repo: str) -> dict:
        """Fetch the latest open PR from a repository."""
        prs = await self._request(
            user_id, "GET",
            f"/repos/{owner}/{repo}/pulls",
            params={"state": "open", "sort": "created", "direction": "desc", "per_page": 1},
        )
        if not prs:
            raise ValueError(f"No open pull requests found in {owner}/{repo}")
        return prs[0]

    async def get_pr_details(self, user_id: str, owner: str, repo: str, pr_number: int) -> dict:
        """Fetch detailed info for a specific PR."""
        return await self._request(user_id, "GET", f"/repos/{owner}/{repo}/pulls/{pr_number}")

    async def get_pr_reviewers(self, user_id: str, owner: str, repo: str, pr_number: int) -> list[str]:
        """Get the list of requested reviewers for a PR."""
        data = await self._request(
            user_id, "GET", f"/repos/{owner}/{repo}/pulls/{pr_number}/requested_reviewers"
        )
        users = data.get("users", []) if isinstance(data, dict) else []
        return [u["login"] for u in users]

    async def get_repo_collaborators(self, user_id: str, owner: str, repo: str) -> list[str]:
        """Fallback: get repository collaborators when PR has no reviewers."""
        collabs = await self._request(user_id, "GET", f"/repos/{owner}/{repo}/collaborators")
        return [c["login"] for c in collabs]


# Singleton
github_service = GitHubService()
