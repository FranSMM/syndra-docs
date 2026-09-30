import pytest
import pytest_asyncio
import httpx
from datetime import datetime, timedelta, timezone
from sqlalchemy import select

from app.models.api_key import APIKey
from app.core.security import get_api_key_hash
from app.core.redis import REDIS_URL
from redis import asyncio as aioredis

# We will run this test inside the docker container so 127.0.0.1:8000 points to the API itself.
BASE_URL = "http://127.0.0.1:8000"
TEST_TICKER = "AAPL"
ENDPOINT = f"/api/v1/sentiment/{TEST_TICKER}?limit=1"
SEMANTIC_ENDPOINT = "/api/v1/search/semantic"


VALID_RAW_KEY = "syndra_test_valid_123"
VALID_HASH = get_api_key_hash(VALID_RAW_KEY)

EXPIRED_RAW_KEY = "syndra_test_expired_123"
EXPIRED_HASH = get_api_key_hash(EXPIRED_RAW_KEY)

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from app.core.config import settings

# Create a dedicated test engine that does NOT pool connections.
# This prevents "Event loop is closed" errors across multiple pytest tests.
test_engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_teardown_db():
    """ Setup test keys in the local database and clean them up afterwards. """
    local_redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    
    # 1. SETUP
    # Clean Redis rate limit and auth cache for the valid key
    await local_redis.delete(f"ratelimit:{VALID_HASH}")
    await local_redis.delete(f"auth:{VALID_HASH}")

    async with TestSessionLocal() as session:
        # Clean any remnants from previous failed test runs
        stmt = select(APIKey).where(APIKey.hashed_key.in_([VALID_HASH, EXPIRED_HASH]))
        result = await session.execute(stmt)
        for key in result.scalars().all():
            await session.delete(key)
        await session.commit()

        # Insert fresh test keys
        valid_key = APIKey(
            hashed_key=VALID_HASH,
            client_name="Test_Valid_Client",
            is_active=True,
            expires_at=None
        )
        expired_key = APIKey(
            hashed_key=EXPIRED_HASH,
            client_name="Test_Expired_Client",
            is_active=True, # Active but expiration date in the past
            expires_at=datetime.now(timezone.utc) - timedelta(days=1)
        )
        session.add(valid_key)
        session.add(expired_key)
        await session.commit()
    
    yield # Let tests run
    
    # 2. TEARDOWN
    # Clean Redis rate limit and auth cache for the valid key again
    await local_redis.delete(f"ratelimit:{VALID_HASH}")
    await local_redis.delete(f"auth:{VALID_HASH}")

    async with TestSessionLocal() as session:
        stmt = select(APIKey).where(APIKey.hashed_key.in_([VALID_HASH, EXPIRED_HASH]))
        result = await session.execute(stmt)
        for key in result.scalars().all():
            await session.delete(key)
        await session.commit()
        
    await local_redis.aclose()



@pytest.mark.asyncio
async def test_403_missing_api_key():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        response = await client.get(ENDPOINT)
        assert response.status_code == 403
        assert "Missing 'X-API-Key' header" in response.json()["detail"]


@pytest.mark.asyncio
async def test_403_invalid_api_key():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        response = await client.get(ENDPOINT, headers={"X-API-Key": "syndra_fake_key_000"})
        assert response.status_code == 403
        assert "Invalid or revoked" in response.json()["detail"]


@pytest.mark.asyncio
async def test_403_expired_trial_key():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        response = await client.get(ENDPOINT, headers={"X-API-Key": EXPIRED_RAW_KEY})
        assert response.status_code == 403
        assert "expired" in response.json()["detail"].lower()
        
        # Verify it was auto-deactivated in DB
        async with TestSessionLocal() as session:
            stmt = select(APIKey).where(APIKey.client_name == "Test_Expired_Client")
            result = await session.execute(stmt)
            key = result.scalars().first()
            assert key.is_active == False


@pytest.mark.asyncio
async def test_200_valid_key_and_rate_limit_headers():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        response = await client.get(ENDPOINT, headers={"X-API-Key": VALID_RAW_KEY})
        
        # Even if the DB has no articles for AAPL, it should return 200 with article_count=0
        assert response.status_code == 200
        
        # Verify rate limit headers injected by middleware
        assert "x-ratelimit-limit" in response.headers
        assert "x-ratelimit-remaining" in response.headers
        assert int(response.headers["x-ratelimit-remaining"]) == 99


@pytest.mark.asyncio
async def test_429_rate_limiting():
    # Exhaust the rate limit (100 requests)
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # Send 100 requests sequentially to exhaust budget
        for _ in range(100):
            await client.get(ENDPOINT, headers={"X-API-Key": VALID_RAW_KEY})
            
        # The 101st request should be blocked
        response = await client.get(ENDPOINT, headers={"X-API-Key": VALID_RAW_KEY})
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.json()["detail"]
        assert "retry-after" in response.headers


@pytest.mark.asyncio
async def test_200_semantic_search_valid_key():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        response = await client.get(f"{SEMANTIC_ENDPOINT}?query=apple%20earnings&limit=1", headers={"X-API-Key": VALID_RAW_KEY})
        
        # Even if the DB has no articles, it should return 200 with results=[]
        assert response.status_code == 200
        
        # Verify rate limit headers injected by middleware
        assert "x-ratelimit-limit" in response.headers
        assert "x-ratelimit-remaining" in response.headers
