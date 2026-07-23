from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import AccountNotFound, DuplicateAccount
from app.models.account import Account
from app.repositories.account_repository import AccountRepository
from app.schemas.account import AccountCreate


class AccountService:
    def __init__(self, repository: AccountRepository) -> None:
        self._accounts = repository

    async def create_account(
        self,
        session: AsyncSession,
        payload: AccountCreate,
    ) -> Account:
        try:
            async with session.begin():
                existing = await self._accounts.get_by_user_id(
                    session,
                    payload.user_id,
                )
                if existing is not None:
                    raise DuplicateAccount(payload.user_id)

                account = Account(
                    user_id=payload.user_id,
                    currency=payload.currency,
                    cash_balance=payload.initial_cash_balance,
                    reserved_cash=Decimal("0"),
                )
                return await self._accounts.add(session, account)
        except IntegrityError as exc:
            raise DuplicateAccount(payload.user_id) from exc

    async def get_account(
        self,
        session: AsyncSession,
        account_id: UUID,
    ) -> Account:
        account = await self._accounts.get_by_id(session, account_id)
        if account is None:
            raise AccountNotFound(account_id)
        return account
