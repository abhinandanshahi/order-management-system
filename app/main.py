import asyncio
import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.broker.fake import FakeBrokerAdapter
from app.broker.worker import broker_event_worker, day_order_expiry_worker
from app.config import get_settings
from app.database import AsyncSessionFactory, engine
from app.domain.exceptions import (
    AccountNotFound,
    BrokerUnavailable,
    DomainError,
    DuplicateAccount,
    DuplicateOrder,
    InsufficientBuyingPower,
    InvalidCancellation,
    InvalidFill,
    InvalidStateTransition,
    OrderNotFound,
)
from app.logging_config import configure_logging
from app.market_data.websocket_client import MarketDataWebSocketClient
from app.schemas.broker import BrokerExecutionEvent

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    event_queue: asyncio.Queue[BrokerExecutionEvent] = asyncio.Queue()
    broker = FakeBrokerAdapter(event_queue, settings)
    app.state.broker_adapter = broker

    tasks = [
        asyncio.create_task(
            broker_event_worker(event_queue, AsyncSessionFactory),
            name="broker-event-worker",
        ),
        asyncio.create_task(
            day_order_expiry_worker(
                session_factory=AsyncSessionFactory,
                broker=broker,
                settings=settings,
            ),
            name="day-order-expiry-worker",
        ),
    ]

    if settings.market_data_enabled:
        market_client = MarketDataWebSocketClient(
            settings=settings,
            session_factory=AsyncSessionFactory,
        )
        tasks.append(
            asyncio.create_task(
                market_client.run(),
                name="market-data-worker",
            )
        )

    logger.info("Application started", extra={"environment": settings.environment})
    try:
        yield
    finally:
        await broker.close()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await engine.dispose()
        logger.info("Application stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "Unhandled request failure",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                },
            )
            raise

        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "Request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response

    @app.exception_handler(DomainError)
    async def domain_exception_handler(
        request: Request,
        exc: DomainError,
    ) -> JSONResponse:
        status_code = 400
        error_code = exc.__class__.__name__
        if isinstance(exc, (OrderNotFound, AccountNotFound)):
            status_code = 404
        elif isinstance(
            exc,
            (
                DuplicateAccount,
                DuplicateOrder,
                InvalidCancellation,
                InvalidStateTransition,
                InvalidFill,
            ),
        ):
            status_code = 409
        elif isinstance(exc, InsufficientBuyingPower):
            status_code = 422
        elif isinstance(exc, BrokerUnavailable):
            status_code = 503

        return JSONResponse(
            status_code=status_code,
            content={
                "error": error_code,
                "message": str(exc),
                "path": request.url.path,
            },
        )

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
