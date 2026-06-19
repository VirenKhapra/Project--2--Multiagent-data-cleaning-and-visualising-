import os
import httpx
import asyncio
import logging
from finflow_agent.jobs.repository import JobRepository

logger = logging.getLogger(__name__)

async def send_backend_callback(result_payload: dict, job_id: str, repository: JobRepository) -> None:
    """
    Sends the execution result payload back to the configured backend callback URL.
    Implements timeouts, retries, and transient failure backoff.
    """
    backend_url = os.environ.get("BACKEND_CALLBACK_URL", "http://backend:8000/api/agent/callback")
    secret = os.environ.get("AGENT_CALLBACK_SECRET", "change-agent-callback-secret")
    
    max_retries = 3
    backoff = 1.0
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    backend_url,
                    json=result_payload,
                    headers={"Authorization": f"Bearer {secret}"}
                )
                if 200 <= response.status_code < 300:
                    logger.info(f"Callback succeeded on attempt {attempt + 1}")
                    return
                
                # Check for non-retryable 4xx client errors (excluding 429)
                if 400 <= response.status_code < 500 and response.status_code != 429:
                    logger.error(f"Callback failed with client error {response.status_code}: {response.text}")
                    break
                    
                logger.warning(f"Callback returned status {response.status_code}, retrying...")
        except Exception as e:
            logger.warning(f"Callback request error on attempt {attempt + 1}: {e}")

            
        if attempt < max_retries - 1:
            await asyncio.sleep(backoff)
            backoff *= 2.0
            
    logger.error("Callback failed all retry attempts.")
    # On final failure, mark job CALLBACK_FAILED but do not erase the successful job result
    await repository.mark_callback_failed(job_id)
