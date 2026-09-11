import asyncio
import httpx
from typing import Tuple
from app.config import settings

async def send_to_erp(summary_payload: dict, max_retries: int = 3, initial_delay: float = 0.5) -> Tuple[bool, str]:
    """
    Dispatches an event summary to the ERP REST API.
    Retries on network/server errors with exponential backoff.
    Returns (success: bool, status_message: str).
    """
    headers = {
        "Authorization": f"Bearer {settings.ERP_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    delay = initial_delay
    last_error = ""

    async with httpx.AsyncClient(timeout=4.0) as client:
        for attempt in range(1, max_retries + 1):
            try:
                resp = await client.post(
                    settings.ERP_API_URL,
                    json=summary_payload,
                    headers=headers
                )
                if resp.status_code in (200, 201):
                    return True, f"Synced on attempt {attempt}"
                
                last_error = f"ERP returned HTTP {resp.status_code}: {resp.text}"
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError) as exc:
                last_error = f"Connection failed ({type(exc).__name__}): {str(exc)}"

            if attempt < max_retries:
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff

    return False, last_error