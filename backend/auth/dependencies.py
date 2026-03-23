"""FastAPI dependencies for injecting the current authenticated user."""

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.middleware import verify_jwt
from backend.database import get_db
from backend.models.user import User


async def get_current_user(
    token_payload: dict = Depends(verify_jwt),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extracts the Auth0 user ID from the verified JWT and returns the
    corresponding User record, creating one if it doesn't exist yet.
    """
    auth0_user_id: str = token_payload.get("sub", "")
    email: str = token_payload.get("email", "")
    name: str | None = token_payload.get("name")

    result = await db.execute(
        select(User).where(User.auth0_user_id == auth0_user_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            auth0_user_id=auth0_user_id,
            email=email,
            name=name,
        )
        db.add(user)
        await db.flush()

    return user
