"""Win-back campaign: personal discount for customers who left. Run by hand, dry run by default.

  python -m bot.services.winback                               # who would get it (nothing is sent or written)
  python -m bot.services.winback --send --confirm-count N      # create offers and send; N must equal the dry-run count
  python -m bot.services.winback --user-ids 123,456 [--send --confirm-count 2]   # explicit users (testing)

Audience: paid at least once, not banned, latest subscription ended 30..180 days ago (so nobody active now),
not offered in this campaign yet. Re-running never sends twice (unique user+campaign).
"""
import argparse
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv
from sqlalchemy import text

from config.settings import get_settings
from db import database_setup
from db.models import PersonalOffer
from bot.middlewares.i18n import get_i18n_instance
from bot.services.offers import discounted
from bot.utils.button_icons import ButtonIconsMiddleware

AUDIENCE_SQL = text("""
    with last_end as (select user_id, max(end_date) e from subscriptions group by user_id)
    select u.user_id from users u join last_end l using (user_id)
    where exists (select 1 from payments p where p.user_id = u.user_id and p.status = 'succeeded')
      and l.e between now() - make_interval(days => :max_days) and now() - make_interval(days => :min_days)
      and not coalesce(u.is_banned, false)
      and not exists (select 1 from personal_offers o where o.user_id = u.user_id and o.campaign = :campaign)
    order by u.user_id
""")


def plan_name(months: int) -> str:
    return {1: "1 месяц", 3: "3 месяца", 6: "6 месяцев", 12: "12 месяцев"}.get(months, f"{months} мес.")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign", default="winback-2026-11")
    ap.add_argument("--pct", type=int, default=50)
    ap.add_argument("--months", default="1,3")
    ap.add_argument("--days", type=int, default=14, help="offer valid for N days")
    ap.add_argument("--min-days", type=int, default=30, help="subscription ended at least N days ago")
    ap.add_argument("--max-days", type=int, default=180, help="... and at most N days ago")
    ap.add_argument("--user-ids", default="", help="explicit users instead of the audience query")
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--confirm-count", type=int, default=-1)
    a = ap.parse_args()

    load_dotenv()
    settings = get_settings()
    factory = database_setup.init_db_connection(settings)
    await database_setup.init_db(settings, factory)  # creates personal_offers if missing
    months = [int(m) for m in a.months.split(",")]

    async with factory() as s:
        if a.user_ids:
            ids = [int(x) for x in a.user_ids.split(",") if x.strip()]
            known = {r[0] for r in await s.execute(text("select user_id from users where user_id = any(:i)"), {"i": ids})}
            done = {r[0] for r in await s.execute(text(
                "select user_id from personal_offers where campaign = :c and user_id = any(:i)"), {"c": a.campaign, "i": ids})}
            ids = [i for i in ids if i in known and i not in done]
        else:
            ids = [r[0] for r in await s.execute(AUDIENCE_SQL, {"min_days": a.min_days, "max_days": a.max_days,
                                                                 "campaign": a.campaign})]
    print(f"campaign {a.campaign}: -{a.pct}% on {months} months, valid {a.days} days")
    print(f"recipients: {len(ids)}   first: {ids[:10]}")
    if not a.send:
        print("dry run: nothing sent. To send: --send --confirm-count", len(ids))
        return
    if a.confirm_count != len(ids):
        print(f"STOP: --confirm-count {a.confirm_count} != {len(ids)} recipients. Nothing sent.")
        return

    i18n = get_i18n_instance(path="locales", default=settings.DEFAULT_LANGUAGE)
    _ = lambda k, **kw: i18n.gettext(settings.DEFAULT_LANGUAGE, k, **kw)
    bot = Bot(settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    bot.session.middleware(ButtonIconsMiddleware(i18n, settings.DEFAULT_LANGUAGE))
    expires = datetime.now(timezone.utc) + timedelta(days=a.days)
    lines = "\n".join(
        _("winback_plan_line", plan=plan_name(m), price=f"{discounted(settings.subscription_options[m], a.pct):.0f}",
          old=f"{settings.subscription_options[m]:.0f}") for m in months)
    msg = _("winback_offer", pct=a.pct, lines=lines, expires=expires.strftime("%d.%m.%Y"))
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=_("winback_buy_button"),
                                                                     callback_data="main_action:subscribe")]])
    stats = {"sent": 0, "blocked": 0, "error": 0}
    for uid in ids:
        async with factory() as s:
            offer = PersonalOffer(user_id=uid, campaign=a.campaign, discount_pct=a.pct, months=a.months,
                                  expires_at=expires)
            s.add(offer)
            await s.commit()  # unique (user, campaign): a second run cannot send twice
            try:
                await bot.send_message(uid, msg, reply_markup=kb)
                offer.send_status = "sent"
            except TelegramForbiddenError:
                offer.send_status = "blocked"
            except TelegramBadRequest as e:
                offer.send_status = "error"
                logging.warning("winback %s: %s", uid, e)
            stats[offer.send_status] += 1
            await s.commit()
        await asyncio.sleep(0.05)  # ~20 messages/s, under Telegram's limit
    print("done:", stats)
    await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
