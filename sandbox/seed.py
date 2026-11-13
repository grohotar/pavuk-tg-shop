"""Fill the sandbox DB and fake panel with test data. Wipes both first.

    python sandbox/seed.py          # run from repo root, needs .env (sandbox one)

Your own ADMIN_IDS[0] gets an active subscription, the rest are fake users
(telegram ids 9000000001+, nobody real can be messaged).
"""
import asyncio
import json
import random
import secrets
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv  # noqa: E402

load_dotenv()
from sqlalchemy import text  # noqa: E402

from config.settings import get_settings  # noqa: E402
from db import database_setup  # noqa: E402
from db.models import (AdAttribution, AdCampaign, Payment, PromoCode,  # noqa: E402
                       PromoCodeActivation, Subscription, User)

random.seed(42)
NOW = datetime.now(timezone.utc)
GB = 2**30
NAMES = ["Аня", "Иван", "Олег", "Маша", "Дима", "Катя", "Саша", "Лена", "Паша", "Юля", "Миша", "Оля"]
PLANS = [(0.25, 149), (1, 289), (3, 789), (6, 1489), (12, 2689)]
PROVIDERS = ["platega", "platega", "yookassa", "stars", "cryptopay"]
PLATFORMS = [("iOS", "iPhone 15", "Happ/4.12"), ("Android", "Pixel 8", "Happ/4.8.0"),
             ("Windows", "PC", "FlClashX/0.4.2"), ("macOS", "MacBook", "INCY/3.9.0")]


def iso(dt):
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


async def main(n_users=60):
    s = get_settings()
    factory = database_setup.init_db_connection(s)
    async with database_setup.async_engine.begin() as c:
        await c.execute(text("DROP SCHEMA public CASCADE"))
        await c.execute(text("CREATE SCHEMA public"))
    await database_setup.init_db(s, factory)

    me = s.ADMIN_IDS[0]
    tg_ids = [me] + [9000000001 + i for i in range(n_users)]
    panel = {"users": [], "devices": {}}
    async with factory() as db:
        camps = [AdCampaign(source=src, start_param=p, cost=c)
                 for src, p, c in [("telegram_ads", "ad_tg1", 5000), ("blogger", "ad_blog", 12000)]]
        promos = [PromoCode(code=c, bonus_days=d, max_activations=m, current_activations=0,
                            created_by_admin_id=me, valid_until=NOW + timedelta(days=30))
                  for c, d, m in [("WELCOME7", 7, 100), ("FRIEND3", 3, 20), ("OLDCODE", 14, 5)]]
        db.add_all(camps + promos)
        await db.flush()

        users = []
        for i, tg in enumerate(tg_ids):
            pid = i + 1
            reg = NOW - timedelta(days=random.randint(1, 200))
            # status mix: active / expiring soon / expired / disabled / never paid
            kind = "active" if tg == me else random.choices(
                ["active", "soon", "expired", "disabled", "none"], [50, 10, 20, 5, 15])[0]
            end = {"active": NOW + timedelta(days=random.randint(10, 300)),
                   "soon": NOW + timedelta(days=random.randint(0, 3), hours=5),
                   "expired": NOW - timedelta(days=random.randint(1, 60)),
                   "disabled": NOW + timedelta(days=20),
                   "none": NOW - timedelta(days=1)}[kind]
            pu = {"id": pid, "uuid": str(uuid.uuid4()), "shortUuid": secrets.token_urlsafe(12)[:16],
                  "username": f"tg_{tg}", "telegramId": tg, "email": None, "description": None, "tag": None,
                  "status": "DISABLED" if kind == "disabled" else "ACTIVE", "expireAt": iso(end),
                  "trafficLimitBytes": 0, "trafficLimitStrategy": "NO_RESET", "hwidDeviceLimit": 0,
                  "activeInternalSquads": [], "createdAt": iso(reg),
                  "userTraffic": {"usedTrafficBytes": random.randint(0, 400) * GB,
                                  "lifetimeUsedTrafficBytes": random.randint(100, 4000) * GB,
                                  "onlineAt": iso(NOW - timedelta(minutes=random.randint(1, 5000)))}}
            panel["users"].append(pu)
            panel["devices"][str(pid)] = [
                {"hwid": secrets.token_hex(8), "platform": p, "osVersion": "", "deviceModel": m,
                 "userAgent": ua, "createdAt": iso(reg), "updatedAt": iso(NOW)}
                for p, m, ua in random.sample(PLATFORMS, random.randint(0, 3))]

            u = User(user_id=tg, username=None,
                     first_name="Я (админ)" if tg == me else random.choice(NAMES),
                     language_code="ru", registration_date=reg, panel_user_uuid=pu["uuid"],
                     panel_user_id=pid, referral_code=secrets.token_hex(4),
                     referred_by_id=random.choice(users).user_id if users and random.random() < 0.2 else None,
                     source=random.choice([None, None, "ad_tg1", "ad_blog"]))
            users.append(u)
            db.add(u)
            await db.flush()
            if u.source:
                db.add(AdAttribution(user_id=tg, ad_campaign_id=camps[0 if u.source == "ad_tg1" else 1].ad_campaign_id))
            if kind == "none":
                continue
            months, price = random.choice(PLANS)
            db.add(Subscription(user_id=tg, panel_user_uuid=pu["uuid"], panel_user_id=pid,
                                panel_subscription_uuid=pu["shortUuid"], start_date=reg, end_date=end,
                                duration_months=max(1, int(months)), is_active=kind in ("active", "soon"),
                                status_from_panel=pu["status"] if kind != "expired" else "EXPIRED",
                                traffic_limit_bytes=0, traffic_used_bytes=pu["userTraffic"]["usedTrafficBytes"],
                                provider=random.choice(PROVIDERS)))
            for k in range(random.randint(1, 4)):
                prov = random.choice(PROVIDERS)
                db.add(Payment(user_id=tg, provider=prov, provider_payment_id=f"sbx-{tg}-{k}",
                               amount=float(price), currency="XTR" if prov == "stars" else "RUB",
                               status=random.choices(["succeeded", "pending", "canceled"], [85, 5, 10])[0],
                               description=f"Подписка {months} мес.", subscription_duration_months=max(1, int(months)),
                               created_at=reg + timedelta(days=30 * k)))
        await db.flush()
        for u in random.sample(users[1:], 8):
            db.add(PromoCodeActivation(promo_code_id=promos[0].promo_code_id, user_id=u.user_id))
        promos[0].current_activations = 8
        await db.commit()

    Path(__file__).with_name("panel_state.json").write_text(json.dumps(panel, ensure_ascii=False, indent=1))
    await database_setup.async_engine.dispose()
    print(f"seeded {len(tg_ids)} users (you: {me}), panel_state.json written")


if __name__ == "__main__":
    asyncio.run(main())
