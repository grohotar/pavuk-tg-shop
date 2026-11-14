"""One reminder, once, to users who started the bot 24-48 h ago and never paid (UNPAID_REMINDER_ENABLED)."""
import asyncio
import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import text

from db.models import SentNotice

KIND = "unpaid_24h"
DUE_SQL = text("""
    select u.user_id from users u
    where u.registration_date between now() - interval '48 hours' and now() - interval '24 hours'
      and not coalesce(u.is_banned, false)
      and not exists (select 1 from payments p where p.user_id = u.user_id and p.status = 'succeeded')
      and not exists (select 1 from subscriptions s where s.user_id = u.user_id and s.end_date > now())
      and not exists (select 1 from sent_notices n where n.user_id = u.user_id and n.kind = :kind)
    limit 200
""")


async def send_due(bot: Bot, settings, i18n, session_factory) -> int:
    _ = lambda k, **kw: i18n.gettext(settings.DEFAULT_LANGUAGE, k, **kw)
    rows = [[InlineKeyboardButton(text=_("menu_subscribe_inline"), callback_data="main_action:subscribe")]]
    if settings.SUPPORT_LINK:
        rows.append([InlineKeyboardButton(text=_("menu_support_button"), url=settings.SUPPORT_LINK)])
    week = settings.subscription_options.get(0)
    msg = _("unpaid_24h_reminder", week_price=f"{week:.0f}" if week else "")
    sent = 0
    async with session_factory() as s:
        ids = [r[0] for r in await s.execute(DUE_SQL, {"kind": KIND})]
        for uid in ids:
            s.add(SentNotice(user_id=uid, kind=KIND))
            await s.commit()  # mark first: never send twice, even if sending fails
            try:
                await bot.send_message(uid, msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
                sent += 1
            except Exception as e:  # blocked the bot etc.
                logging.info("unpaid reminder to %s not delivered: %s", uid, e)
            await asyncio.sleep(0.05)
    return sent


async def run(bot: Bot, settings, i18n, session_factory, interval: int = 600) -> None:
    while True:
        try:
            n = await send_due(bot, settings, i18n, session_factory)
            if n:
                logging.info("unpaid reminder: sent %s", n)
        except Exception:
            logging.exception("unpaid reminder loop failed")
        await asyncio.sleep(interval)
