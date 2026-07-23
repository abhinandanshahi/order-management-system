from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.dependencies import (
    DbSession,
    get_cancellation_service,
    get_order_repository,
    get_order_service,
)
from app.domain.enums import OrderStatus
from app.domain.exceptions import OrderNotFound
from app.repositories.order_repository import OrderRepository
from app.schemas.order import (
    CancelOrderResponse,
    FillResponse,
    OrderCreate,
    OrderEventResponse,
    OrderResponse,
)
from app.services.cancellation_service import CancellationService
from app.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate,
    session: DbSession,
    service: Annotated[OrderService, Depends(get_order_service)],
) -> OrderResponse:
    order = await service.create_order(session, payload)
    return OrderResponse.model_validate(order)


@router.get("", response_model=list[OrderResponse])
async def list_orders(
    session: DbSession,
    service: Annotated[OrderService, Depends(get_order_service)],
    account_id: UUID | None = None,
    order_status: OrderStatus | None = Query(default=None, alias="status"),
    open_only: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[OrderResponse]:
    orders = await service.list_orders(
        session,
        account_id=account_id,
        status=order_status,
        open_only=open_only,
        limit=limit,
        offset=offset,
    )
    return [OrderResponse.model_validate(order) for order in orders]


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    session: DbSession,
    service: Annotated[OrderService, Depends(get_order_service)],
) -> OrderResponse:
    order = await service.get_order(session, order_id)
    return OrderResponse.model_validate(order)


@router.post(
    "/{order_id}/cancel",
    response_model=CancelOrderResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def cancel_order(
    order_id: UUID,
    session: DbSession,
    service: Annotated[CancellationService, Depends(get_cancellation_service)],
) -> CancelOrderResponse:
    order = await service.request_cancellation(session, order_id)
    return CancelOrderResponse(
        order_id=order.id,
        status=order.status,
        message="Cancellation request accepted",
    )


@router.get("/{order_id}/fills", response_model=list[FillResponse])
async def list_order_fills(
    order_id: UUID,
    session: DbSession,
    repository: Annotated[OrderRepository, Depends(get_order_repository)],
) -> list[FillResponse]:
    order = await repository.get_by_id(session, order_id)
    if order is None:
        raise OrderNotFound(order_id)
    fills = await repository.list_fills(session, order_id)
    return [FillResponse.model_validate(fill) for fill in fills]


@router.get("/{order_id}/events", response_model=list[OrderEventResponse])
async def list_order_events(
    order_id: UUID,
    session: DbSession,
    repository: Annotated[OrderRepository, Depends(get_order_repository)],
) -> list[OrderEventResponse]:
    order = await repository.get_by_id(session, order_id)
    if order is None:
        raise OrderNotFound(order_id)
    events = await repository.list_events(session, order_id)
    return [OrderEventResponse.model_validate(event) for event in events]
