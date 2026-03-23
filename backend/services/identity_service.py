"""Identity mapping service — resolves GitHub usernames to Slack/Google identities."""

from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.identity_mapping import IdentityMapping
from backend.services.slack_service import slack_service


class IdentityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve_github_to_email(self, user_id: str, github_username: str) -> str | None:
        """Look up email for a GitHub username. Returns None if unresolved."""
        result = await self.db.execute(
            select(IdentityMapping).where(
                IdentityMapping.user_id == user_id,
                IdentityMapping.github_username == github_username,
            )
        )
        mapping = result.scalar_one_or_none()
        return mapping.email if mapping else None

    async def resolve_github_to_slack(self, user_id: str, github_username: str) -> str | None:
        """Look up Slack user ID for a GitHub username. Returns None if unresolved."""
        result = await self.db.execute(
            select(IdentityMapping).where(
                IdentityMapping.user_id == user_id,
                IdentityMapping.github_username == github_username,
            )
        )
        mapping = result.scalar_one_or_none()
        return mapping.slack_user_id if mapping else None

    async def save_mapping(
        self,
        user_id: str,
        github_username: str,
        email: str | None = None,
        slack_user_id: str | None = None,
        display_name: str | None = None,
        confidence_score: float = 1.0,
    ) -> IdentityMapping:
        """Persist a new identity mapping (or update if exists)."""
        result = await self.db.execute(
            select(IdentityMapping).where(
                IdentityMapping.user_id == user_id,
                IdentityMapping.github_username == github_username,
            )
        )
        mapping = result.scalar_one_or_none()

        if mapping is None:
            mapping = IdentityMapping(
                user_id=user_id,
                github_username=github_username,
            )
            self.db.add(mapping)

        if email is not None:
            mapping.email = email
        if slack_user_id is not None:
            mapping.slack_user_id = slack_user_id
        if display_name is not None:
            mapping.display_name = display_name
        mapping.confidence_score = confidence_score

        await self.db.flush()
        return mapping

    async def get_unresolved(self, user_id: str, usernames: list[str]) -> list[str]:
        """Return GitHub usernames that have no identity mapping for this user."""
        unresolved = []
        for username in usernames:
            result = await self.db.execute(
                select(IdentityMapping).where(
                    IdentityMapping.user_id == user_id,
                    IdentityMapping.github_username == username,
                )
            )
            mapping = result.scalar_one_or_none()
            if mapping is None or (mapping.email is None and mapping.slack_user_id is None):
                unresolved.append(username)
        return unresolved

    async def fuzzy_match_slack(
        self, user_id: str, github_username: str, channel_id: str
    ) -> dict | None:
        """
        Attempt to match a GitHub username to a Slack user by display name similarity.
        Resolution priority #2 (after DB lookup, before manual resolution).
        """
        try:
            members = await slack_service.get_channel_members(user_id, channel_id)
        except Exception:
            return None

        best_match = None
        best_score = 0.0

        for member in members:
            for name_field in ["display_name", "real_name", "name"]:
                name = member.get(name_field, "").lower()
                if not name:
                    continue
                score = SequenceMatcher(None, github_username.lower(), name).ratio()
                if score > best_score and score > 0.6:
                    best_score = score
                    best_match = member

        if best_match:
            return {
                "slack_user_id": best_match["id"],
                "display_name": best_match.get("real_name", best_match.get("name", "")),
                "confidence_score": best_score,
            }
        return None
