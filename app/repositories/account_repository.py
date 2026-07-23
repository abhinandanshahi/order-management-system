from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account


class AccountRepository:
    async def add(self, session: AsyncSession, account: Account) -> Account:
        session.add(account)
        await session.flush()
        return account

    async def get_by_id(
        self,
        session: AsyncSession,
        account_id: UUID,
    ) -> Account | None:
        return await session.get(Account, account_id)

    async def get_for_update(
        self,
        session: AsyncSession,
        account_id: UUID,
    ) -> Account | None:
        result = await session.execute(
            select(Account)
            .where(Account.id == account_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(
        self,
        session: AsyncSession,
        user_id: str,
    ) -> Account | None:
        result = await session.execute(
            select(Account).where(Account.user_id == user_id)
        )
        return result.scalar_one_or_none()
