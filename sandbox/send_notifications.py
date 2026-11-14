"""Sandbox: send all panel expiration notifications to a Telegram ID via the test bot.
   .venv/bin/python sandbox/send_notifications.py <telegram_id>
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from aiogram import Bot  # noqa: E402
from aiogram.client.default import DefaultBotProperties  # noqa: E402
from config.settings import get_settings  # noqa: E402
from db import database_setup  # noqa: E402
from bot.middlewares.i18n import get_i18n_instance  # noqa: E402
from bot.services.panel_webhook_service import PanelWebhookService  # noqa: E402


async def main(tg: int):
    s = get_settings()
    s.SUBSCRIPTION_NOTIFICATIONS_ENABLED = True  # off in the sandbox .env
    factory = database_setup.init_db_connection(s)
    bot = Bot(s.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    svc = PanelWebhookService(bot, s, get_i18n_instance(path="locales", default=s.DEFAULT_LANGUAGE), factory, None)
    sent = []
    orig = bot.send_message
    async def counting_send(*a, **kw):
        sent.append(await orig(*a, **kw))
    bot.send_message = counting_send
    now = datetime.now(timezone.utc)
    for hours in (-72, -48, -24):
        await svc.handle_event("user.expiration", {"telegramId": tg, "expireAt": (now - timedelta(hours=hours)).isoformat()},
                               {"expiration": hours})
    await svc.handle_event("user.expired", {"telegramId": tg, "expireAt": now.isoformat()})
    await svc.handle_event("user.expiration", {"telegramId": tg, "expireAt": (now - timedelta(days=1)).isoformat()},
                           {"expiration": 24})
    await bot.session.close()
    print(f"sent {len(sent)} messages to {tg}")

asyncio.run(main(int(sys.argv[1])))
