"""Auth and connections API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user
from backend.auth.token_vault import token_vault_client
from backend.config import get_settings
from backend.database import get_db
from backend.models.user import User
from backend.models.connected_account import ConnectedAccount
from backend.schemas import (
    UserResponse,
    ConnectedAccountResponse,
    ConnectionStartResponse,
    ConnectionStatus,
)

settings = get_settings()
router = APIRouter(tags=["auth"])

# Valid provider names for Token Vault connections
VALID_PROVIDERS = {"github", "google", "slack"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the current authenticated user profile."""
    return current_user


@router.get("/connections", response_model=list[ConnectedAccountResponse])
async def list_connections(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all connected service accounts for the current user."""
    result = await db.execute(
        select(ConnectedAccount).where(ConnectedAccount.user_id == current_user.id)
    )
    return result.scalars().all()


@router.post("/connections/{provider}/start", response_model=ConnectionStartResponse)
async def start_connection(
    provider: str,
    current_user: User = Depends(get_current_user),
):
    """Initiate the Token Vault OAuth flow for a provider."""
    if provider not in VALID_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    callback_url = f"{settings.API_BASE_URL}/api/connections/{provider}/callback"
    redirect_url = await token_vault_client.initiate_connection(
        user_id=current_user.auth0_user_id,
        connection=provider,
        callback_url=callback_url,
    )
    return ConnectionStartResponse(redirect_url=redirect_url)


@router.get("/connections/{provider}/callback")
async def connection_callback(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Handle OAuth callback — create/update the connected_account record (no raw token stored)."""
    if provider not in VALID_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    # Check if record already exists
    result = await db.execute(
        select(ConnectedAccount).where(
            ConnectedAccount.user_id == current_user.id,
            ConnectedAccount.provider == provider,
        )
    )
    account = result.scalar_one_or_none()

    if account is None:
        account = ConnectedAccount(
            user_id=current_user.id,
            provider=provider,
            status=ConnectionStatus.CONNECTED.value,
        )
        db.add(account)
    else:
        account.status = ConnectionStatus.CONNECTED.value

    await db.flush()
    return {"status": "connected", "provider": provider}


@router.delete("/connections/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_provider(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke Token Vault entry and remove the connected_account record."""
    if provider not in VALID_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    try:
        await token_vault_client.revoke_connection(
            user_id=current_user.auth0_user_id,
            connection=provider,
        )
    except Exception:
        pass  # Best-effort revocation

    await db.execute(
        delete(ConnectedAccount).where(
            ConnectedAccount.user_id == current_user.id,
            ConnectedAccount.provider == provider,
        )
    )
