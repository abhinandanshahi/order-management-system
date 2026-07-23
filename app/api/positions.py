from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies import DbSession, get_pnl_service, get_position_repository
from app.domain.exceptions import AccountNotFound
from app.repositories.account_repository import AccountRepository
from app.repositories.position_repository import PositionRepository
from app.schemas.position import PnLSummaryResponse, PositionResponse
from app.services.pnl_service import PnLService

router = APIRouter(prefix="/accounts/{account_id}", tags=["positions"])


async def _ensure_account_exists(session: DbSession, account_id: UUID) -> None:
    account = await AccountRepository().get_by_id(session, account_id)
    if account is None:
        raise AccountNotFound(account_id)


@router.get("/positions", response_model=list[PositionResponse])
async def list_positions(
    account_id: UUID,
    session: DbSession,
    repository: Annotated[PositionRepository, Depends(get_position_repository)],
) -> list[PositionResponse]:
    await _ensure_account_exists(session, account_id)
    positions = await repository.list_by_account(session, account_id)
    return [PositionResponse.model_validate(position) for position in positions]


@router.get("/pnl", response_model=PnLSummaryResponse)
async def get_pnl_summary(
    account_id: UUID,
    session: DbSession,
    service: Annotated[PnLService, Depends(get_pnl_service)],
) -> PnLSummaryResponse:
    await _ensure_account_exists(session, account_id)
    return await service.get_account_summary(session, account_id)
