# Order Management System

A FastAPI service that models the lifecycle of a client order from submission to its final outcome. It validates orders, reserves buying power, routes valid orders to a simulated asynchronous broker, processes full and partial fills, supports cancellation, maintains positions and cash, and marks unrealized P&L using the latest known market price.

This service is intentionally an OMS rather than an exchange or matching engine. Broker fills are simulated by `FakeBrokerAdapter`; market data is used only for position marking.

## Engineering goals

The implementation emphasizes correctness around financial state:

- PostgreSQL transactions for every multi-record financial operation
- `SELECT ... FOR UPDATE` for order, account, and position mutations
- Unique idempotency keys for client order submission
- Unique broker event IDs and execution IDs
- Append-only order audit history
- Centralized and deterministic state transitions
- `Decimal` and PostgreSQL `NUMERIC(24, 8)` for financial values
- Dependency inversion through `BrokerAdapter`
- Deterministic tests using controlled broker behavior

## Technology

- Python 3.12+
- FastAPI
- PostgreSQL 16
- SQLAlchemy 2.0 Async and asyncpg
- Alembic
- Pydantic v2 and Pydantic Settings
- pytest, pytest-asyncio, HTTPX
- Docker and Docker Compose

## Project structure

```text
order-management-system/
├── app/
│   ├── api/                # HTTP endpoints only
│   ├── broker/             # BrokerAdapter, fake broker, workers
│   ├── domain/             # Enums, exceptions, state machine
│   ├── market_data/        # Pricing WebSocket integration
│   ├── models/             # SQLAlchemy ORM models
│   ├── repositories/       # Database access
│   ├── schemas/            # Pydantic request/response models
│   ├── services/           # Business workflows and transactions
│   ├── config.py
│   ├── database.py
│   ├── dependencies.py
│   └── main.py
├── tests/
│   ├── unit/
│   └── integration/
├── alembic/
├── docker/
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## Order lifecycle

The centralized state machine supports these principal journeys:

```text
NEW -> VALIDATED -> ROUTED -> PARTIALLY_FILLED -> FILLED
NEW -> REJECTED
ROUTED -> REJECTED
ROUTED/PARTIALLY_FILLED -> CANCEL_PENDING -> CANCELLED
CANCEL_PENDING -> FILLED
```

`CANCEL_PENDING -> FILLED` is intentional. A final fill may win the race against a pending cancellation at the broker. Both execution and cancellation processing lock the order row and reevaluate the latest committed state.

Terminal states are `FILLED`, `REJECTED`, and `CANCELLED`.

## Time-in-force behavior

- **GTC** remains open until filled or cancelled.
- **IOC** applies the immediate broker fill, then cancels any remainder in the same database transaction. It never rests.
- **DAY** receives an `expires_at` value when created. A background expiry worker requests cancellation after the configured demo session duration.

`DAY_ORDER_EXPIRY_SECONDS` is configurable because this assignment does not define an exchange calendar or trading-session timezone.

## Transaction and concurrency strategy

### Order creation

A transaction locks the account, checks idempotency and buying power, creates the order and audit entries, reserves cash for a buy order, and moves the order to `ROUTED`. The broker is notified only after the transaction commits.

### Fill processing

A broker event transaction:

1. Locks the order row.
2. Checks whether the broker event has already been processed.
3. Validates the event against the current order state and remaining quantity.
4. Inserts an immutable fill.
5. Locks and updates the account.
6. Locks or creates the position.
7. Updates quantities, average prices, cash, and P&L.
8. Appends an order event.
9. Records the broker event outcome.
10. Commits all changes atomically.

The order lock serializes duplicate and simultaneous callbacks for the same order. Database constraints provide a second line of defense.

### Quantity conservation

The database enforces:

```text
filled_quantity + cancelled_quantity + remaining_quantity = quantity
```

It also rejects negative quantities, prices, cash, reserved cash, and remaining quantity.

### Idempotency

- `(account_id, idempotency_key)` is unique.
- `(account_id, client_order_id)` is unique.
- `broker_event_id` is unique.
- `execution_id` is unique.

Repeating the same valid submission returns the existing order. Reusing its idempotency key with different order content returns a conflict. Repeated broker events do not change cash or positions twice.

## Financial model

### Cash

`cash_balance` represents settled account cash. `reserved_cash` is the portion held for open buy orders. Available buying power is:

```text
cash_balance - reserved_cash
```

A buy fill reduces both settled cash and the order's proportional reservation. A rejection or cancellation releases only the unfilled reservation. Sell fills increase cash.

### Positions

Positions are updated only after confirmed execution events. The position algorithm supports:

- Increasing long and short positions
- Partially closing a position
- Fully closing a position
- Crossing from long to short or short to long
- Weighted average entry price
- Realized P&L on the closed quantity

Signed net quantity makes unrealized P&L work for both directions:

```text
(mark_price - average_entry_price) * net_quantity
```

### Market data

The WebSocket client reads its URL and subscription symbols from environment variables. It accepts common `symbol`/`price` field variants, stores the latest tick, and updates unrealized P&L for affected positions.

Market data never creates fills. Credentials and URLs are not committed.

## Run locally with Docker

Copy the environment file:

```bash
cp .env.example .env
```

Start PostgreSQL and the API:

```bash
docker compose up --build
```

The application will run migrations before starting.

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

Stop services:

```bash
docker compose down
```

Remove database volumes when a completely clean environment is required:

```bash
docker compose down -v
```

## Database migrations

```bash
docker compose run --rm api alembic upgrade head
```

Create a new migration after changing models:

```bash
docker compose run --rm api alembic revision --autogenerate -m "describe change"
```

## Run tests

The Compose environment creates both `oms` and `oms_test`. It also sets `RUN_INTEGRATION_TESTS=true`, so the complete suite runs against PostgreSQL:

```bash
docker compose run --rm api pytest -q
```

Run linting:

```bash
docker compose run --rm api ruff check app tests
```

Outside Docker, unit tests run without PostgreSQL. Integration and concurrency tests are skipped unless explicitly enabled:

```bash
pytest tests/unit -q
```

To run all tests outside Docker:

```bash
export TEST_DATABASE_URL=postgresql+asyncpg://oms:oms@localhost:5432/oms_test
export RUN_INTEGRATION_TESTS=true
pytest -q
```

## API examples

### Create account

```bash
curl -X POST http://localhost:8000/api/v1/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "client-1001",
    "initial_cash_balance": "100000.00",
    "currency": "INR"
  }'
```

### Submit order

```bash
curl -X POST http://localhost:8000/api/v1/orders \
  -H "Content-Type: application/json" \
  -d '{
    "client_order_id": "ORDER-1001",
    "idempotency_key": "client-1001-order-1001",
    "account_id": "<account-uuid>",
    "symbol": "RELIANCE",
    "side": "BUY",
    "order_type": "LIMIT",
    "time_in_force": "GTC",
    "quantity": "100",
    "price": "1450.50"
  }'
```

### Query open orders

```bash
curl "http://localhost:8000/api/v1/orders?account_id=<account-uuid>&open_only=true"
```

### Cancel order

```bash
curl -X POST http://localhost:8000/api/v1/orders/<order-uuid>/cancel
```

### Positions and P&L

```bash
curl http://localhost:8000/api/v1/accounts/<account-uuid>/positions
curl http://localhost:8000/api/v1/accounts/<account-uuid>/pnl
```

## Error responses

Expected domain errors are translated centrally. A typical response is:

```json
{
  "error": "InvalidCancellation",
  "message": "Order cannot be cancelled from FILLED",
  "path": "/api/v1/orders/.../cancel"
}
```

Not-found errors return `404`, conflicts return `409`, validation errors return `422`, and broker availability failures return `503`.

## Important design decisions

### Why PostgreSQL instead of SQLite?

The assignment requires protection against simultaneous fills, cancellations, lost updates, and double processing. PostgreSQL row-level locks and constraints make these guarantees testable and meaningful. SQLite would hide or change several concurrency behaviors.

### Why an in-process fake broker queue?

The assignment asks for a simulated asynchronous adapter, not a durable messaging platform. The adapter abstraction keeps OMS logic independent of the implementation. A real deployment can replace it with a Kafka, RabbitMQ, or broker SDK adapter without changing order services.

### Why store both current order state and events?

The order table supports fast current-state queries. The event table provides an immutable audit history for support, debugging, and reconciliation. Events are appended; existing history is never updated.

### Why reject malformed broker events instead of correcting them?

Silently capping an overfill would hide an upstream defect and could make reconciliation impossible. Invalid or stale callbacks are recorded as ignored broker events with an audit reason.

## Known limitations

- The fake broker queue is process-local and is intended for a single API instance. A durable external queue is required for multi-instance delivery guarantees.
- Broker submission occurs after the order transaction commits. A production integration would normally add a transactional outbox so dispatch survives a process failure between commit and publish.
- The DAY session is represented by a configurable duration, not a holiday-aware exchange calendar.
- Authentication, authorization, fees, taxes, corporate actions, settlement, and regulatory reporting are outside this assignment.
- The request price is used as the simulated execution price. A real broker decides execution price and applies market-specific rules.
- Short selling is allowed by the simplified position model; borrow availability and margin checks are not modeled.
- The market feed payload is normalized defensively because the assignment does not define a formal tick schema.
