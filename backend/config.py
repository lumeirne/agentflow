"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    """AgentFlow configuration — all values come from .env or environment."""

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./agentflow.db"

    # Auth0 — core tenant
    AUTH0_DOMAIN: str = ""
    AUTH0_CLIENT_ID: str = ""
    AUTH0_CLIENT_SECRET: str = ""
    AUTH0_AUDIENCE: str = ""

    # Auth0 — Token Vault / My Account API
    # Custom API client used for token exchange (may differ from the main SPA client)
    AUTH0_TV_CLIENT_ID: str = ""
    AUTH0_TV_CLIENT_SECRET: str = ""
    # My Account API audience (e.g. "https://<domain>/api/v2/")
    AUTH0_MY_ACCOUNT_AUDIENCE: str = ""

    # Provider connection aliases as registered in Auth0
    # Override if your tenant uses non-default connection names
    AUTH0_GITHUB_CONNECTION: str = "github"
    AUTH0_GOOGLE_CONNECTION: str = "google-oauth2"
    AUTH0_SLACK_CONNECTION: str = "slack"

    # LLM
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = ""

    # App
    SECRET_KEY: str = ""
    APP_BASE_URL: str = "http://localhost:3000"
    API_BASE_URL: str = "http://localhost:8000"

    # Load env values from stable absolute paths so startup CWD does not matter.
    model_config = SettingsConfigDict(
        env_file=(
            str(ROOT_DIR / ".env"),
            str(BACKEND_DIR / ".env"),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
