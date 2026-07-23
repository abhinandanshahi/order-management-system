import os
from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://oms:oms@localhost:5432/oms_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["MARKET_DATA_ENABLED"] = "false"
os.environ.setdefault("BROKER_MIN_DELAY_SECONDS", "0")
os.environ.setdefault("BROKER_MAX_DELAY_SECONDS", "0")

from app import models  # noqa: E402, F401
from app.database import AsyncSessionFactory, Base, engine  # noqa: E402
from app.dependencies import get_broker_adapter  # noqa: E402
from app.main import app  # noqa: E402
from tests.support import RecordingBroker  # noqa: E402


@pytest_asyncio.fixture(scope="session", autouse=True)
async def database_schema() -> AsyncIterator[None]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(autouse=True)
async def clean_database(database_schema) -> AsyncIterator[None]:
    async with AsyncSessionFactory() as session:
        async with session.begin():
            await session.execute(
                text(
                    "TRUNCATE TABLE processed_broker_events, order_events, fills, "
                    "positions, orders, market_prices, accounts RESTART IDENTITY CASCADE"
                )
            )
    yield


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionFactory() as session:
        yield session
        if session.in_transaction():
            await session.rollback()


@pytest.fixture
def recording_broker() -> RecordingBroker:
    return RecordingBroker()


@pytest_asyncio.fixture
async def api_client(recording_broker: RecordingBroker) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_broker_adapter] = lambda: recording_broker
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client
    app.dependency_overrides.clear()


@pytest.fixture
def account_payload() -> dict:
    return {
        "user_id": "user-1001",
        "initial_cash_balance": str(Decimal("100000.00")),
        "currency": "INR",
    }
