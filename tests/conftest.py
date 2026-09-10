import pytest
import redis.asyncio as aioredis
import app.main as main_module
from app.config import settings


@pytest.fixture(autouse=True)
async def setup_redis():
    """Initialize real Redis connection before each test and tear down after.
    Flushes the DB so dedup keys from prior runs don't bleed into assertions.
    """
    main_module.redis_client = aioredis.from_url(
        settings.REDIS_URL, decode_responses=False
    )
    await main_module.redis_client.flushdb()
    yield
    await main_module.redis_client.aclose()
    main_module.redis_client = None
