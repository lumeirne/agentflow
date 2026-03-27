import asyncio
import json
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import async_session_factory, Base, engine
from backend.models.user import User
from backend.models.connected_account import ConnectedAccount
from backend.models.workflow_run import WorkflowRun
from backend.schemas import RunStatus
from backend.utils.logger import get_logger

logger = get_logger(__name__)

async def seed_demo_data():
    """Seeds the local SQLite database with initial demo data."""
    logger.info("Dropping and recreating tables")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        
    logger.info("Inserting seed data")
    async with async_session_factory() as db:
        # Create user
        demo_user = User(
            id="demo-user-123",
            auth0_user_id="auth0|demo123",
            email="demo@agentflow.ai",
            name="Demo Agent Flow User"
        )
        db.add(demo_user)
        
        # Add demo connections (status=connected but no actual tokens)
        github_conn = ConnectedAccount(
            user_id=demo_user.id,
            provider="github",
            status="connected",
            scopes_json=json.dumps(["repo", "user"])
        )
        google_conn = ConnectedAccount(
            user_id=demo_user.id,
            provider="google",
            status="connected",
            scopes_json=json.dumps(["calendar.readonly", "gmail.compose"])
        )
        db.add_all([github_conn, google_conn])
        
        # Add a mock historic workflow run
        sample_prompt = "Schedule a meeting with the frontend team to unblock the current release."
        recent_run = WorkflowRun(
            id="run_demo_83901",
            user_id=demo_user.id,
            prompt=sample_prompt,
            status=RunStatus.COMPLETED.value,
            parsed_intent_json=json.dumps({
                "workflow_type": "meeting_scheduler",
                "steps": [
                    {"step_key": "fetch_members", "action_type": "identity_resolve"},
                    {"step_key": "freebusy", "action_type": "calendar_freebusy"}
                ]
            }),
            result_summary="Successfully scheduled a 30m meeting with Alex and Maya for tomorrow at 2 PM.",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(recent_run)
        
        await db.commit()
    logger.info("Seed data inserted successfully")

if __name__ == "__main__":
    asyncio.run(seed_demo_data())
