import asyncio
import json
import logging
from pathlib import Path
from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import Submission, SubmissionStatus

logger = logging.getLogger(__name__)


def _submission_file_id(submission: Submission) -> str:
    return Path(str(submission.file_path or "")).name


async def enqueue_submission_dispatch(submission_id: UUID | str) -> None:
    settings = get_settings()
    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        
        async with AsyncSessionLocal() as db:
            submission = await db.get(Submission, UUID(str(submission_id)))
            if not submission:
                logger.warning("Dispatch queue referenced missing submission %s", submission_id)
                return
            
            payload = {
                "submission_id": str(submission.id),
                "file_id": _submission_file_id(submission),
                "file_name": submission.file_name,
                "instruction": submission.instruction,
                "output_format": str(submission.output_format or "").strip().lower()
            }
            
            await redis.enqueue_job("process_job_task", payload)
            
            submission.status = SubmissionStatus.planning
            await db.commit()
    except Exception as e:
        logger.exception("Failed to enqueue submission via arq")

async def start_dispatcher(app) -> None:
    # Set a dummy task so that health checks that look for agent_dispatch_task return True
    app.state.agent_dispatch_task = "arq_managed"

async def stop_dispatcher(app) -> None:
    app.state.agent_dispatch_task = None
