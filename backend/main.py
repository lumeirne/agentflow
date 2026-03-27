"""AgentFlow — FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.database import init_db
from backend.schemas import HealthResponse

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # Import models so Base.metadata sees all tables
    import backend.models  # noqa: F401
    await init_db()
    yield


app = FastAPI(
    title="AgentFlow API",
    description="Multi-service productivity co-pilot powered by Auth0 Token Vault",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        settings.APP_BASE_URL,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register API routers ──
from backend.api.auth import router as auth_router
from backend.api.runs import router as runs_router
from backend.api.approvals import router as approvals_router
from backend.api.settings import router as settings_router

app.include_router(auth_router, prefix="/api")
app.include_router(runs_router, prefix="/api")
app.include_router(approvals_router, prefix="/api")
app.include_router(settings_router, prefix="/api")


# ── Health check ──
@app.get("/api/health", response_model=HealthResponse, tags=["health"])
async def health():
    return HealthResponse()


@app.get("/api/health/auth0", tags=["health"])
async def health_auth0():
    """
    Validate Auth0 tenant prerequisites for Token Vault operation.
    Returns warnings if Management API, MRRT, or Token Vault grants are not reachable.
    """
    from backend.auth.token_vault import token_vault_client
    warnings = []
    try:
        await token_vault_client.get_management_token()
    except Exception as e:
        warnings.append(f"Auth0 Management API unreachable: {e}")

    return {
        "status": "ok" if not warnings else "degraded",
        "warnings": warnings,
        "token_source": "auth0_token_vault",
    }


# ── WebSocket endpoint ──
from backend.websocket.manager import ws_manager


@app.websocket("/ws/runs/{run_id}")
async def websocket_endpoint(websocket: WebSocket, run_id: str):
    """Stream real-time workflow step events to the frontend."""
    await ws_manager.connect(run_id, websocket)
    try:
        while True:
            # Keep connection alive; client can send pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(run_id, websocket)
