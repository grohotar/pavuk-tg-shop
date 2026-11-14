import asyncio
import hashlib
import hmac
import json
import os
import logging
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any, Tuple

from aiohttp import ClientSession, ClientTimeout, web
from aiogram import Bot
from sqlalchemy.orm import sessionmaker

from config.settings import Settings
from bot.middlewares.i18n import JsonI18n
from bot.services.subscription_service import SubscriptionService
from bot.services.referral_service import ReferralService
from bot.keyboards.inline.user_keyboards import get_connect_and_main_keyboard
from bot.services.notification_service import NotificationService
from db.dal import payment_dal, user_dal, platega_subscription_dal
from bot.keyboards.inline.user_keyboards import get_subscribe_only_markup
from bot.services.offers import mark_offer_used
from bot.utils.text_sanitizer import sanitize_display_name, username_for_display


class PlategaService:
    def __init__(
        self,
        *,
        bot: Bot,
        settings: Settings,
        i18n: JsonI18n,
        async_session_factory: sessionmaker,
        subscription_service: SubscriptionService,
        referral_service: ReferralService,
    ):
        self.bot = bot
        self.settings = settings
        self.i18n = i18n
        self.async_session_factory = async_session_factory
        self.subscription_service = subscription_service
        self.referral_service = referral_service

        self.merchant_id: Optional[str] = settings.PLATEGA_MERCHANT_ID
        self.secret_key: Optional[str] = settings.PLATEGA_SECRET_KEY
        self.default_currency: str = (settings.DEFAULT_CURRENCY_SYMBOL or "RUB").upper()

        self.api_base_url: str = os.getenv("PLATEGA_API_BASE_URL", "https://app.platega.io")  # sandbox overrides
        self._timeout = ClientTimeout(total=45)
        self._session: Optional[ClientSession] = None

        self.configured: bool = bool(
            settings.PLATEGA_ENABLED and self.merchant_id and self.secret_key
        )
        if not self.configured:
            logging.warning("PlategaService initialized but not fully configured. Payments disabled.")

    @staticmethod
    def _format_amount(amount: float) -> str:
        """Format amount with two decimal places."""
        quantized = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return f"{quantized:.2f}"

    async def create_payment(
        self,
        *,
        payment_db_id: int,
        user_id: int,
        months: int,
        amount: float,
        currency: Optional[str] = None,
        payment_method: Optional[int] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Create a payment link via Platega API.
        Returns (success, response_data)
        """
        if not self.configured:
            logging.error("PlategaService is not configured. Cannot create payment.")
            return False, {"message": "service_not_configured"}

        currency_code = (currency or self.default_currency or "RUB").upper()
        # Amount should be integer (in smallest currency unit or whole units)
        amount_int = int(amount)

        # Prepare request payload according to Platega API docs
        # Format description based on subscription period
        if months == 0:
            description = "Подписка на 1 неделю"
        else:
            description = f"Подписка на {months} мес."
        
        payload: Dict[str, Any] = {
            "paymentMethod": payment_method or 2,  # Default to SBP (2)
            "paymentDetails": {
                "amount": amount_int,
                "currency": currency_code,
            },
            "description": description,
            "payload": f"user_id:{user_id};months:{months};payment_db_id:{payment_db_id}",
            "return": "https://t.me/pipun_bot",  # Return URL after successful payment
            "failedUrl": "https://t.me/pipun_bot",  # URL for failed payment
        }

        session = await self._get_session()
        url = f"{self.api_base_url}/transaction/process"

        headers = {
            "X-MerchantId": self.merchant_id,
            "X-Secret": self.secret_key,
            "Content-Type": "application/json",
        }

        try:
            async with session.post(url, json=payload, headers=headers) as response:
                response_text = await response.text()
                try:
                    response_data = json.loads(response_text) if response_text else {}
                except json.JSONDecodeError:
                    logging.error("Platega create_payment: failed to decode JSON: %s", response_text)
                    return False, {"status": response.status, "message": "invalid_json", "raw": response_text}

                if response.status not in (200, 201):
                    logging.error(
                        "Platega create_payment: API returned error (status=%s, body=%s)",
                        response.status,
                        response_data,
                    )
                    return False, {"status": response.status, "message": response_data}

                return True, response_data
        except Exception as exc:
            logging.error("Platega create_payment: request failed: %s", exc, exc_info=True)
            return False, {"message": str(exc)}

    async def check_payment_status(self, transaction_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Check payment status via Platega API.
        Returns (success, response_data)
        """
        if not self.configured:
            logging.error("PlategaService is not configured. Cannot check status.")
            return False, {"message": "service_not_configured"}

        session = await self._get_session()
        url = f"{self.api_base_url}/transaction/{transaction_id}"

        headers = {
            "X-MerchantId": self.merchant_id,
            "X-Secret": self.secret_key,
        }

        try:
            async with session.get(url, headers=headers) as response:
                response_text = await response.text()
                try:
                    response_data = json.loads(response_text) if response_text else {}
                except json.JSONDecodeError:
                    logging.error("Platega check_status: failed to decode JSON: %s", response_text)
                    return False, {"status": response.status, "message": "invalid_json", "raw": response_text}

                if response.status != 200:
                    logging.error(
                        "Platega check_status: API returned error (status=%s, body=%s)",
                        response.status,
                        response_data,
                    )
                    return False, {"status": response.status, "message": response_data}

                return True, response_data
        except Exception as exc:
            logging.error("Platega check_status: request failed: %s", exc, exc_info=True)
            return False, {"message": str(exc)}

    # ---------------- autopay (Platega subscription, paymentMethod 6) ----------------

    async def _api(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any]]:
        session = await self._get_session()
        headers = {"X-MerchantId": self.merchant_id, "X-Secret": self.secret_key, "Content-Type": "application/json"}
        try:
            async with session.request(method, f"{self.api_base_url}{path}", json=body, headers=headers) as resp:
                text = await resp.text()
                try:
                    data = json.loads(text) if text else {}
                except json.JSONDecodeError:
                    data = {"raw": text}
                if resp.status not in (200, 201):
                    logging.error("Platega %s %s: HTTP %s %s", method, path, resp.status, data)
                    return False, data
                return True, data
        except Exception as exc:
            logging.error("Platega %s %s failed: %s", method, path, exc, exc_info=True)
            return False, {"message": str(exc)}

    async def create_subscription(self, *, user_id: int, months: int, amount: float, description: str) -> Tuple[bool, Dict[str, Any]]:
        """Autopay: Platega charges `amount` every `months` months via SBP. First charge on payer's consent."""
        return await self._api("POST", "/transaction/process", {
            "paymentMethod": 6,
            "paymentDetails": {"amount": int(amount), "currency": self.default_currency,
                               "interval": "3", "intervalCount": months},  # 3 = month
            "description": description,
            "payload": f"autopay;user_id:{user_id};months:{months}",
            "return": "https://t.me/pipun_bot",
            "failedUrl": "https://t.me/pipun_bot",
        })

    async def cancel_subscription(self, subscription_id: str) -> bool:
        ok, _ = await self._api("POST", f"/subscription/{subscription_id}/cancel")
        return ok

    @staticmethod
    def _parse_dt(value: Any) -> Optional[datetime]:
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else None
        except ValueError:
            return None

    async def _payment_for_subscription_charge(self, session, sub_id: str, transaction_id: str, payload: Dict[str, Any]):
        sub = await platega_subscription_dal.get(session, sub_id)
        if not sub:
            logging.error(f"Platega autopay: charge {transaction_id} for unknown subscription {sub_id}")
            return None
        first_charge = sub.status == "pending"
        sub.status = "active"
        sub.next_charge_at = self._parse_dt(payload.get("nextChargeAt")) or sub.next_charge_at
        payment = await payment_dal.create_payment_record(session, {
            "user_id": sub.user_id,
            "amount": float(payload.get("amount") or sub.amount),
            "currency": payload.get("currency") or self.default_currency,
            "status": "pending_platega",
            "description": f"Автопродление, {sub.months} мес.",
            "subscription_duration_months": sub.months,
            "provider": "platega",
            "provider_payment_id": transaction_id,
        })
        payment.autopay_kind = "new" if first_charge else "renewal"  # for the admin notification only
        return payment

    async def _notify(self, user_id: int, key: str, markup=None, **kw) -> None:
        try:
            await self.bot.send_message(user_id, self.i18n.gettext(self.settings.DEFAULT_LANGUAGE, key, **kw),
                                        reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Platega autopay: failed to notify {user_id}: {e}")

    async def _on_subscription_status(self, sub_id: str, status: str, payload: Dict[str, Any]) -> None:
        async with self.async_session_factory() as session:
            sub = await platega_subscription_dal.get(session, sub_id)
            if not sub:
                logging.warning(f"Platega autopay: {status} for unknown subscription {sub_id}")
                return
            prev = sub.status
            sub.status = {"SUBSCRIPTION_ACTIVATED": "active", "SUBSCRIPTION_PAST_DUE": "past_due",
                          "SUBSCRIPTION_CANCELLED": "cancelled", "SUBSCRIPTION_FAILED": "failed"}.get(status, prev)
            sub.next_charge_at = self._parse_dt(payload.get("nextChargeAt")) or sub.next_charge_at
            await session.commit()
            logging.info(f"Platega autopay: subscription {sub_id} {prev} -> {sub.status} ({status})")
            # Cancelled outside the bot (payer via bank/e-mail): tell the user. Bot-side cancel already said so.
            if status == "SUBSCRIPTION_CANCELLED" and prev != "cancelled":
                await self._notify(sub.user_id, "autopay_cancelled_external")

    async def _on_subscription_charge_failed(self, sub_id: str) -> None:
        async with self.async_session_factory() as session:
            sub = await platega_subscription_dal.get(session, sub_id)
            if not sub:
                return
            sub.status = "past_due"
            await session.commit()
            await self._notify(sub.user_id, "autopay_charge_failed",
                               markup=get_subscribe_only_markup(self.settings.DEFAULT_LANGUAGE, self.i18n),
                               amount=f"{sub.amount:.0f}")

    async def _get_session(self) -> ClientSession:
        if self._session is None or self._session.closed:
            self._session = ClientSession(timeout=self._timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    def _validate_signature(self, request_headers: Dict[str, str]) -> bool:
        """
        Validate webhook signature from Platega.
        Platega sends X-MerchantId and X-Secret headers.
        """
        merchant_id = request_headers.get("X-MerchantId") or request_headers.get("x-merchantid")
        secret = request_headers.get("X-Secret") or request_headers.get("x-secret")

        if not merchant_id or not secret:
            return False

        if merchant_id != self.merchant_id:
            return False

        if secret != self.secret_key:
            return False

        return True

    async def webhook_route(self, request: web.Request) -> web.Response:
        """
        Handle Platega webhook callbacks.
        Platega sends status updates: CONFIRMED (success) or CANCELED (failed).
        """
        if not self.configured:
            return web.Response(status=503, text="platega_disabled")

        # Validate signature via headers
        headers_dict = {k: v for k, v in request.headers.items()}
        if not self._validate_signature(headers_dict):
            logging.error("Platega webhook: invalid signature or merchant mismatch")
            return web.Response(status=403, text="invalid_signature")

        try:
            payload = await request.json()
        except Exception as e:
            logging.error(f"Platega webhook: failed to read JSON: {e}")
            return web.Response(status=400, text="bad_request")
        return await self.process_callback(payload)

    async def process_callback(self, payload: Dict[str, Any]) -> web.Response:
        """Handle one Platega callback body (already authenticated)."""

        # Log incoming webhook data for debugging
        logging.info(f"Platega webhook received payload: {payload}")

        # Platega callback format: id, amount, currency, status, paymentMethod
        transaction_id = payload.get("id")
        status = payload.get("status")
        amount_value = payload.get("amount")
        
        # Try to extract payment_db_id from 'payload' field (our custom data)
        custom_payload = payload.get("payload", "")
        order_id_str = None
        if custom_payload:
            # Parse "user_id:123;months:1;payment_db_id:456"
            for part in str(custom_payload).split(";"):
                if part.startswith("payment_db_id:"):
                    order_id_str = part.split(":")[1]
                    break
        
        # If no custom payload, try to find payment by transaction_id
        if not order_id_str and transaction_id:
            # We'll look up by provider_payment_id later
            order_id_str = None
        
        amount_str = str(amount_value) if amount_value else None

        if not transaction_id or not status:
            logging.error(f"Platega webhook: missing required fields. transaction_id={transaction_id}, status={status}")
            return web.Response(status=400, text="missing_data")

        # Autopay (Platega subscription): status events and failed charges
        sub_id = payload.get("subscriptionId")
        if str(status).startswith("SUBSCRIPTION_"):
            await self._on_subscription_status(sub_id or transaction_id, status, payload)
            return web.Response(text="OK")
        if sub_id and status == "CANCELED":
            await self._on_subscription_charge_failed(sub_id)
            return web.Response(text="OK")

        # Only process CONFIRMED payments
        if status != "CONFIRMED":
            logging.info(f"Platega webhook: payment {transaction_id} status is {status}, ignoring")
            return web.Response(text="OK")

        async with self.async_session_factory() as session:
            payment = None
            
            # First try to find by order_id if available
            if order_id_str:
                try:
                    payment_db_id = int(order_id_str)
                    payment = await payment_dal.get_payment_by_db_id(session, payment_db_id)
                except (TypeError, ValueError):
                    logging.warning(f"Platega webhook: invalid order_id value '{order_id_str}'")
            
            # If not found, try to find by provider_payment_id (transaction_id)
            if not payment:
                payment = await payment_dal.get_payment_by_provider_payment_id(session, str(transaction_id))
            
            # A charge of an autopay subscription has no payment record yet: create it
            if not payment and sub_id:
                payment = await self._payment_for_subscription_charge(session, sub_id, str(transaction_id), payload)

            if not payment:
                logging.error(f"Platega webhook: payment not found for transaction_id={transaction_id}, order_id={order_id_str}")
                return web.Response(status=404, text="payment_not_found")

            if payment.status == "succeeded":
                logging.info(f"Platega webhook: payment {payment.payment_id} already succeeded")
                return web.Response(text="OK")

            # Optional amount verification
            if amount_str:
                try:
                    amount_decimal = Decimal(amount_str)
                    expected_amount = Decimal(str(payment.amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    if amount_decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) != expected_amount:
                        logging.warning(
                            f"Platega webhook: amount mismatch for payment {payment.payment_id} "
                            f"(expected {expected_amount}, got {amount_decimal})"
                        )
                except Exception as e:
                    logging.warning(f"Platega webhook: failed to compare amount for payment {payment.payment_id}: {e}")

            activation = None
            referral_bonus = None
            try:
                await payment_dal.update_provider_payment_and_status(
                    session=session,
                    payment_db_id=payment.payment_id,
                    provider_payment_id=str(transaction_id),
                    new_status="succeeded",
                )

                months = payment.subscription_duration_months if payment.subscription_duration_months is not None else 1

                activation = await self.subscription_service.activate_subscription(
                    session,
                    payment.user_id,
                    months,
                    float(payment.amount),
                    payment.payment_id,
                    provider="platega",
                )

                referral_bonus = await self.referral_service.apply_referral_bonuses_for_payment(
                    session,
                    payment.user_id,
                    months,
                    current_payment_db_id=payment.payment_id,
                    skip_if_active_before_payment=False,
                )

                await mark_offer_used(session, self.settings, payment.user_id, months,
                                      float(payment.amount), payment.payment_id)

                await session.commit()
            except Exception as e:
                await session.rollback()
                logging.error(f"Platega webhook: failed to process payment {payment.payment_id}: {e}", exc_info=True)
                return web.Response(status=500, text="processing_error")

            db_user = await user_dal.get_user_by_id(session, payment.user_id)
            lang = db_user.language_code if db_user and db_user.language_code else self.settings.DEFAULT_LANGUAGE
            _ = lambda k, **kw: self.i18n.gettext(lang, k, **kw) if self.i18n else k

            config_link = None
            final_end = None
            months = payment.subscription_duration_months if payment.subscription_duration_months is not None else 1
            if activation:
                config_link = activation.get("subscription_url")
                final_end = activation.get("end_date")

            applied_days = 0
            if referral_bonus and referral_bonus.get("referee_new_end_date"):
                final_end = referral_bonus["referee_new_end_date"]
                applied_days = referral_bonus.get("referee_bonus_applied_days", 0)

            if not final_end and activation and activation.get("end_date"):
                final_end = activation["end_date"]

            if not config_link:
                config_link = _("config_link_not_available")
            if final_end:
                end_date_str = final_end.strftime("%Y-%m-%d")
            else:
                end_date_str = _("config_link_not_available")

            if applied_days:
                inviter_name_display = _("friend_placeholder")
                if db_user and db_user.referred_by_id:
                    inviter = await user_dal.get_user_by_id(session, db_user.referred_by_id)
                    if inviter:
                        safe_name = sanitize_display_name(inviter.first_name) if inviter.first_name else None
                        if safe_name:
                            inviter_name_display = safe_name
                        elif inviter.username:
                            inviter_name_display = username_for_display(inviter.username, with_at=False)
                text = _(
                    "payment_successful_with_referral_bonus_full",
                    months=months,
                    base_end_date=activation["end_date"].strftime("%Y-%m-%d") if activation and activation.get("end_date") else end_date_str,
                    bonus_days=applied_days,
                    final_end_date=end_date_str,
                    inviter_name=inviter_name_display,
                    config_link=config_link,
                )
            else:
                if months == 0:
                    text = _(
                        "payment_successful_full_week",
                        end_date=end_date_str,
                        config_link=config_link,
                    )
                else:
                    text = _(
                        "payment_successful_full",
                        months=months,
                        end_date=end_date_str,
                        config_link=config_link,
                    )

            order_info_text = _(
                "platega_order_full",
                order_id=transaction_id,
                date=datetime.now().strftime("%Y-%m-%d"),
            )
            if order_info_text:
                text = f"{order_info_text}\n{text}"
            if sub_id:
                sub = await platega_subscription_dal.get(session, sub_id)
                if sub and sub.next_charge_at:
                    text += "\n\n" + _("autopay_next_charge_line", date=sub.next_charge_at.strftime("%d.%m.%Y"),
                                       amount=f"{sub.amount:.0f}")

            markup = get_connect_and_main_keyboard(
                lang,
                self.i18n,
                self.settings,
                config_link,
                preserve_message=True,
            )
            try:
                await self.bot.send_message(
                    payment.user_id,
                    text,
                    reply_markup=markup,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            except Exception as e:
                logging.error(f"Platega notification: failed to send message to user {payment.user_id}: {e}")

            try:
                notification_service = NotificationService(self.bot, self.settings, self.i18n)
                # Count user's succeeded payments (including this one)
                payment_count = await payment_dal.count_user_succeeded_payments(session, payment.user_id)
                await notification_service.notify_payment_received(
                    user_id=payment.user_id,
                    amount=float(payment.amount),
                    currency=self.default_currency,
                    months=months,
                    payment_provider="platega",
                    username=db_user.username if db_user else None,
                    payment_number=payment_count,
                    autopay=getattr(payment, "autopay_kind", None),
                )
            except Exception as e:
                logging.error(f"Platega notification: failed to notify admins: {e}")

        return web.Response(text="OK")


async def platega_webhook_route(request: web.Request) -> web.Response:
    service: PlategaService = request.app["platega_service"]
    return await service.webhook_route(request)
