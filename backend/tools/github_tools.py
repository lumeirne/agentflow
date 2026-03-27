"""GitHub tool functions — used by the LangGraph agent executor node.

Typed provider errors (ProviderConnectionMissingError, ProviderTokenExpiredError, etc.)
are propagated unchanged so the executor can branch on recoverability.
"""

from backend.services.github_service import github_service
# Re-export typed errors so callers can import from one place
from backend.auth.token_vault import (  # noqa: F401
    ProviderConnectionMissingError,
    ProviderTokenExpiredError,
    ProviderTokenExchangeError,
    ProviderTemporaryError,
    ProviderError,
)


async def github_get_latest_pr(user_id: str, repo: str) -> dict:
    """Fetch the latest open PR. repo format: 'owner/repo'."""
    parts = repo.split("/")
    if len(parts) != 2:
        raise ValueError(f"repo must be in 'owner/repo' format, got: {repo}")
    owner, repo_name = parts
    return await github_service.get_latest_pr(user_id, owner, repo_name)


async def github_get_pr_details(user_id: str, repo: str, pr_number: int) -> dict:
    """Fetch details for a specific PR."""
    owner, repo_name = repo.split("/")
    return await github_service.get_pr_details(user_id, owner, repo_name, pr_number)


async def github_get_pr_reviewers(user_id: str, repo: str, pr_number: int) -> list[str]:
    """Get requested reviewers for a PR."""
    owner, repo_name = repo.split("/")
    return await github_service.get_pr_reviewers(user_id, owner, repo_name, pr_number)


async def github_get_repo_collaborators(user_id: str, repo: str) -> list[str]:
    """Fallback: get repo collaborators when PR has no reviewers."""
    owner, repo_name = repo.split("/")
    return await github_service.get_repo_collaborators(user_id, owner, repo_name)
