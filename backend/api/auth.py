"""Auth and connections API routes."""

from fastapi import APIRouter, Body, Depends, HTTPException, status
from typing import Any, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user
from backend.auth.token_vault import (
    token_vault_client,
    ProviderConnectionMissingError,
    ProviderTokenExpiredError,
    ProviderTemporaryError,
)
from backend.config import get_settings
from backend.database import get_db
from backend.models.user import User
from backend.models.connected_account import ConnectedAccount
from backend.utils.logger import get_logger
from backend.schemas import (
    UserResponse,
    ConnectedAccountResponse,
    ConnectionStartResponse,
    ConnectionStatus,
)

settings = get_settings()
router = APIRouter(tags=["auth"])
logger = get_logger(__name__)

# Valid provider names for Token Vault connections
VALID_PROVIDERS = {"github", "google", "slack"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the current authenticated user profile."""
    logger.info("Returning current user profile", extra={"data": {"user_id": current_user.id}})
    return current_user


@router.get("/connections", response_model=list[ConnectedAccountResponse])
async def list_connections(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all connected service accounts for the current user."""
    logger.info("Listing connected accounts", extra={"data": {"user_id": current_user.id}})
    result = await db.execute(
        select(ConnectedAccount).where(ConnectedAccount.user_id == current_user.id)
    )
    accounts = result.scalars().all()
    logger.info(
        "Connected accounts fetched",
        extra={"data": {"user_id": current_user.id, "count": len(accounts)}},
    )
    return accounts


@router.post("/connections/{provider}/start", response_model=ConnectionStartResponse)
async def start_connection(
    provider: str,
    current_user: User = Depends(get_current_user),
    body: Optional[dict[str, Any]] = Body(default=None),
):
    """Initiate the OAuth flow for a provider via Auth0 social connection."""
    logger.info(
        "Starting provider connection",
        extra={"data": {"provider": provider, "user_id": current_user.id}},
    )
    if provider not in VALID_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    # Optional: caller may pass return_to_run_id so the callback can redirect
    # back to the originating run page after connection succeeds.
    return_to_run_id: str | None = None
    if body:
        return_to_run_id = body.get("return_to_run_id")

    callback_url = f"{settings.APP_BASE_URL}/api/connections/{provider}/callback"
    redirect_url = await token_vault_client.initiate_connection(
        user_id=current_user.auth0_user_id,
        connection=provider,
        callback_url=callback_url,
        return_to_run_id=return_to_run_id,
    )
    logger.info(
        "Generated provider redirect URL",
        extra={
            "data": {
                "provider": provider,
                "user_id": current_user.id,
                "return_to_run_id": return_to_run_id,
            }
        },
    )
    return ConnectionStartResponse(redirect_url=redirect_url)


@router.post("/connections/{provider}/callback")
async def connection_callback(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    body: Optional[dict[str, Any]] = Body(default=None),
):
    """
    Mark a provider as connected and link the identity to the user's account.

    Stores only connection metadata (status, external_account_id) — never
    provider access tokens. Tokens are retrieved on-demand from Auth0 Token Vault.
    """
    logger.info(
        "Handling connection callback",
        extra={
            "data": {
                "provider": provider,
                "user_id": current_user.id,
                "auth0_user_id": current_user.auth0_user_id,
                "has_body": bool(body),
                "token_source": "auth0_token_vault",
            }
        },
    )
    if provider not in VALID_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    idp_sub: str | None = None
    if body:
        idp_sub = body.get("idp_sub")

    # ── STEP 1: Link the secondary account to primary account ──────────────
    # This is critical: Auth0's /authorize doesn't auto-link, so we must do it
    link_succeeded = False
    if idp_sub:
        logger.info(
            "Attempting to link secondary identity to primary account",
            extra={
                "data": {
                    "provider": provider,
                    "primary_user_id": current_user.auth0_user_id,
                    "secondary_user_id": idp_sub,
                }
            },
        )

        link_succeeded = await token_vault_client.link_accounts(
            primary_user_id=current_user.auth0_user_id,
            secondary_provider=provider,
            secondary_user_id=idp_sub,
        )

        if link_succeeded:
            logger.info(
                "Account link succeeded - identity should now be accessible",
                extra={
                    "data": {
                        "provider": provider,
                        "primary_user_id": current_user.auth0_user_id,
                        "secondary_user_id": idp_sub,
                    }
                },
            )
        else:
            logger.warning(
                "Account link failed - connection will be stored but tokens may not work",
                extra={
                    "data": {
                        "provider": provider,
                        "primary_user_id": current_user.auth0_user_id,
                    }
                },
            )

    # ── STEP 2: Store connection metadata (regardless of linking status) ───
    await token_vault_client.store_connection_metadata(
        db=db,
        user_id=current_user.id,
        connection=provider,
        external_account_id=idp_sub,
    )
    logger.info(
        "Connection metadata stored (Auth0 Token Vault is token source)",
        extra={
            "data": {
                "provider": provider,
                "user_id": current_user.id,
                "link_succeeded": link_succeeded,
                "token_source": "auth0_token_vault",
            }
        },
    )

    # ── STEP 3: Return status based on linking result ──────────────────────
    if link_succeeded:
        return {
            "status": "connected",
            "provider": provider,
            "linked": True,
            "message": f"{provider} identity has been linked to your account",
        }
    else:
        return {
            "status": "connected",
            "provider": provider,
            "linked": False,
            "message": f"{provider} connection stored - if tokens don't work, try reconnecting",
        }


@router.delete("/connections/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_provider(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove the connected_account record and best-effort revoke from Token Vault."""
    logger.info(
        "Disconnecting provider",
        extra={"data": {"provider": provider, "user_id": current_user.id}},
    )
    if provider not in VALID_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    # Best-effort Token Vault revocation
    await token_vault_client.revoke_connection(
        user_id=current_user.auth0_user_id,
        connection=provider,
    )

    # Delete DB record
    await db.execute(
        delete(ConnectedAccount).where(
            (ConnectedAccount.user_id == current_user.id) &
            (ConnectedAccount.provider == provider)
        )
    )
    logger.info(
        "Disconnected provider and removed DB account",
        extra={"data": {"provider": provider, "user_id": current_user.id}},
    )
