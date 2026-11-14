from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import PlategaSubscription

LIVE = ("active", "past_due")


async def get(session: AsyncSession, subscription_id: str) -> Optional[PlategaSubscription]:
    return await session.get(PlategaSubscription, subscription_id)


async def get_live_for_user(session: AsyncSession, user_id: int) -> Optional[PlategaSubscription]:
    """Active or past-due autopay of the user, newest first."""
    res = await session.execute(
        select(PlategaSubscription)
        .where(PlategaSubscription.user_id == user_id, PlategaSubscription.status.in_(LIVE))
        .order_by(PlategaSubscription.created_at.desc())
        .limit(1))
    return res.scalar_one_or_none()


async def create(session: AsyncSession, **fields) -> PlategaSubscription:
    sub = PlategaSubscription(**fields)
    session.add(sub)
    await session.flush()
    return sub
