from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.dependencies import DbSession, get_account_service
from app.schemas.account import AccountCreate, AccountResponse
from app.services.account_service import AccountService

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: AccountCreate,
    session: DbSession,
    service: Annotated[AccountService, Depends(get_account_service)],
) -> AccountResponse:
    account = await service.create_account(session, payload)
    return AccountResponse.model_validate(account)


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: UUID,
    session: DbSession,
    service: Annotated[AccountService, Depends(get_account_service)],
) -> AccountResponse:
    account = await service.get_account(session, account_id)
    return AccountResponse.model_validate(account)
