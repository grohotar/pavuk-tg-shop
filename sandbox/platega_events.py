"""Sandbox only: deliver fake Platega callbacks to the bot running in polling mode.

The fake Platega (sandbox/fake-panel.js) queues callbacks instead of POSTing them (the bot on the Mac has no
public webhook). This loop pulls the queue and calls PlategaService.process_callback, the same handler
the prod webhook /webhook/platega runs after checking X-MerchantId / X-Secret.
"""
import asyncio
import logging


async def poll(platega_service, interval: float = 2.0) -> None:
    url = f"{platega_service.api_base_url}/sandbox/platega-events"
    headers = {"X-MerchantId": platega_service.merchant_id or "", "X-Secret": platega_service.secret_key or ""}
    logging.info("SANDBOX: polling fake Platega events from %s", url)
    while True:
        try:
            session = await platega_service._get_session()
            async with session.get(url, headers=headers) as resp:
                events = await resp.json() if resp.status == 200 else []
            for event in events:
                logging.info("SANDBOX: fake Platega callback %s", event)
                resp = await platega_service.process_callback(event)
                logging.info("SANDBOX: bot answered %s %s", resp.status, resp.text)
        except Exception:
            logging.exception("SANDBOX: fake Platega poll failed")
        await asyncio.sleep(interval)
