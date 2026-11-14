"""Prices are computed on the server (never taken from callback data) and include a personal offer if any."""
import math
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import Settings
from db.models import PersonalOffer


async def active_offer(session: AsyncSession, user_id: int) -> Optional[PersonalOffer]:
    res = await session.execute(
        select(PersonalOffer)
        .where(PersonalOffer.user_id == user_id, PersonalOffer.used_payment_id.is_(None),
               PersonalOffer.expires_at > datetime.now(timezone.utc))
        .order_by(PersonalOffer.discount_pct.desc())
        .limit(1))
    return res.scalar_one_or_none()


def offer_months(offer: PersonalOffer) -> set:
    return {int(m) for m in offer.months.split(",") if m.strip()}


def discounted(price: float, pct: int) -> float:
    return float(math.ceil(price * (100 - pct) / 100))


async def price_for(session: AsyncSession, settings: Settings, user_id: int, months: int) -> Optional[float]:
    """Price the user pays for `months` (0 = week), or None if there is no such plan."""
    base = settings.subscription_options.get(months)
    if base is None:
        return None
    offer = await active_offer(session, user_id)
    if offer and months in offer_months(offer):
        return discounted(base, offer.discount_pct)
    return float(base)


async def mark_offer_used(session: AsyncSession, settings: Settings, user_id: int, months: int,
                          amount: float, payment_id: int) -> Optional[PersonalOffer]:
    """Called after a successful payment: a discounted purchase consumes the offer (returned)."""
    offer = await active_offer(session, user_id)
    base = settings.subscription_options.get(months)
    if offer and base and months in offer_months(offer) and amount < base:
        offer.used_payment_id = payment_id
        return offer
    return None
