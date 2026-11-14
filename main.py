import asyncio
import logging
import os
import re
import sys

from dotenv import load_dotenv

from bot.main_bot import run_bot
from config.settings import get_settings, Settings
from db.database_setup import init_db, init_db_connection


class _SecretMask(logging.Filter):
    """Replace secret values (bot token, DB password, API keys) in every log line."""

    def __init__(self, secrets):
        super().__init__()
        self.secrets = sorted(secrets, key=len, reverse=True)

    def filter(self, record):
        msg = record.getMessage()
        masked = msg
        for s in self.secrets:
            masked = masked.replace(s, "***")
        if masked != msg:
            record.msg, record.args = masked, None
        return True


def _install_secret_mask():
    secrets = {v for k, v in os.environ.items()
               if re.search(r"TOKEN|SECRET|PASSWORD|_KEY", k) and len(v) >= 12}
    secrets |= {m.group(1) for v in os.environ.values()
                for m in [re.search(r"://[^:/@]+:([^@]{12,})@", v)] if m}
    for h in logging.getLogger().handlers:
        h.addFilter(_SecretMask(secrets))


async def main():
    load_dotenv()
    settings = get_settings()

    session_factory = init_db_connection(settings)
    if not session_factory:
        logging.critical(
            "Failed to initialize DB connection and session factory. Exiting.")
        return

    await init_db(settings, session_factory)

    await run_bot(settings)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    load_dotenv()
    _install_secret_mask()
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped manually")
    except Exception as e_global:
        logging.critical(f"Global unhandled exception in main: {e_global}",
                         exc_info=True)
        sys.exit(1)
