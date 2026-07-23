import asyncio
import json
import logging
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import websockets
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.repositories.market_data_repository import MarketDataRepository
from app.repositories.position_repository import PositionRepository
from app.services.market_data_service import MarketDataService

logger = logging.getLogger(__name__)


class MarketDataWebSocketClient:
    def __init__(
        self,
        *,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._service = MarketDataService(
            MarketDataRepository(),
            PositionRepository(),
        )

    async def run(self) -> None:
        if not self._settings.market_data_url:
            logger.warning("Market data is enabled but MARKET_DATA_URL is not set")
            return

        while True:
            try:
                async with websockets.connect(
                    self._settings.market_data_url,
                    ping_interval=20,
                    ping_timeout=20,
                ) as websocket:
                    await self._subscribe(websocket)
                    async for raw_message in websocket:
                        for tick in self._extract_ticks(raw_message):
                            async with self._session_factory() as session:
                                await self._service.apply_tick(session, **tick)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Market data connection failed")
                await asyncio.sleep(self._settings.market_data_reconnect_seconds)

    async def _subscribe(self, websocket) -> None:
        if self._settings.market_data_symbols:
            await websocket.send(
                json.dumps(
                    {
                        "action": "subscribe",
                        "symbols": self._settings.market_data_symbols,
                    }
                )
            )

    @staticmethod
    def _extract_ticks(raw_message: str | bytes) -> list[dict[str, Any]]:
        try:
            payload = json.loads(raw_message)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Ignoring non-JSON market data message")
            return []

        records = payload if isinstance(payload, list) else [payload]
        ticks: list[dict[str, Any]] = []
        for record in records:
            if not isinstance(record, dict):
                continue

            symbol = record.get("symbol") or record.get("s")
            raw_price = (
                record.get("price")
                or record.get("ltp")
                or record.get("last_price")
                or record.get("p")
            )
            if not symbol or raw_price is None:
                continue

            try:
                price = Decimal(str(raw_price))
            except InvalidOperation:
                continue
            if price <= 0:
                continue

            raw_timestamp = record.get("timestamp") or record.get("time")
            observed_at = MarketDataWebSocketClient._parse_timestamp(raw_timestamp)
            ticks.append(
                {
                    "symbol": str(symbol).upper(),
                    "price": price,
                    "observed_at": observed_at,
                }
            )
        return ticks

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime:
        if isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp /= 1000
            return datetime.fromtimestamp(timestamp, tz=UTC)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
            except ValueError:
                pass
        return datetime.now(UTC)
