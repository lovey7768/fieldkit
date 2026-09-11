import pytest
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from app.config import settings
import app.main as main_module
import app.database as _db

# ================================================================
# Patch the module-level engine with NullPool BEFORE any test
# module imports AsyncSessionLocal. NullPool creates a fresh DB
# connection per operation — zero cross-loop binding issues even
# when each test function runs in its own event loop.
# ================================================================
_test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
_test_sessionmaker = async_sessionmaker(
    bind=_test_engine, class_=AsyncSession, expire_on_commit=False
)
_db.engine = _test_engine
_db.AsyncSessionLocal = _test_sessionmaker


@pytest.fixture(autouse=True)
async def setup_redis():
    """Create a fresh Redis client per test function and flush DB for a clean slate.
    Function-scoped so each test's Redis client stays within its own event loop.
    """
    main_module.redis_client = aioredis.from_url(
        settings.REDIS_URL, decode_responses=False
    )
    await main_module.redis_client.flushdb()
    yield
    await main_module.redis_client.aclose()
    main_module.redis_client = None
