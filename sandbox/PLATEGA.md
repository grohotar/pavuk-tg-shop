# Platega API — конспект (docs.platega.io, прочитано 14.11.2026)

База `https://app.platega.io`, заголовки `X-MerchantId`, `X-Secret`, JSON.

## Платёж
`POST /transaction/process`
- `paymentMethod`: 2 СБП QR, 3 ЕРИП, 11 карты (МИР), 12 международные карты, 13 крипта, 14 SberPay, 6 подписка.
- `paymentDetails {amount, currency}`, `description`, `return`, `failedUrl` (обязательны по ручке), `payload` (строка, вернётся в callback), `orderId`.
- `metadata` (обязателен по ручке): `user_email` — e-mail покупателя или `{telegram_id}@telegram.org`, один покупатель = один адрес; без него форма спрашивает e-mail. `userId` — для некоторых категорий обязателен (иначе антифрод выключен, магазин могут отключить), `userName`.
- Ответ: `transactionId`, `redirect`, `status` (PENDING), `expiresIn`.
- `POST /v2/transaction/process` — без `paymentMethod`, способ выбирает плательщик.

`GET /transaction/{id}` — статус и детали. Статусы: PENDING, CONFIRMED, CANCELED, CHARGEBACKED.

## Callback
URL один на мерчанта (ЛК → Настройки → Callback URLs), HTTPS. POST JSON, заголовки `X-MerchantId`, `X-Secret` (подписи нет — сравнивать с своими).
Тело: `id`, `amount`, `currency`, `status`, `paymentMethod`, `payload`, + по ситуации `paymentLinkId`, `subscriptionId`, `nextChargeAt`, `refundId`, `refundAmount`, `refundedAmount`, `refundableAmount`, `refundStatus`. Пустые поля не передаются.
Статусы: CONFIRMED (выдавать товар), CANCELED, CHARGEBACKED (полный возврат), PARTIALLY_REFUNDED, DISPUTED (проверка; потом CONFIRMED или CHARGEBACKED).
Ответ 200; иначе/таймаут 30 с — повтор через 5, 10, 15 мин (всего 3 попытки), дальше вручную из ЛК. Порядок не гарантирован, дедуп по `id`.

## Подписка (paymentMethod 6, автосписание через СБП)
- Создание: `POST /transaction/process` `{paymentMethod:6, paymentDetails:{amount, currency, interval (1 день,2 неделя,3 месяц,4 год), intervalCount}, description, metadata.user_email}` → `transactionId` = subscriptionId, `redirect` на форму. Плательщик подтверждает привязку в банке за 30 мин, иначе Failed.
- Списывает Platega сама. Каждое списание — callback CONFIRMED с `subscriptionId`, `nextChargeAt`; неудача — CANCELED с `subscriptionId` (подписка остаётся).
- События подписки (id = subscriptionId): SUBSCRIPTION_ACTIVATED, SUBSCRIPTION_PAST_DUE, SUBSCRIPTION_CANCELLED (мерчант или плательщик по ссылке из письма), SUBSCRIPTION_FAILED.
- `GET /subscription/{id}`, `GET /subscription?status&from&to&page&size`, `POST /subscription/{id}/cancel` (идемпотентно), `GET /subscription/{id}/update-supported`, `POST /subscription/{id}/update {amount, nextChargeAt, intervalUnit+intervalCount}` — до 5000 ₽ за вызов, со следующего списания, для Active/PastDue.
- Пробный период: подписка на 1 ₽, после активации `update` с полной суммой и датой.

## Возвраты
`GET /transaction/{id}/cancel-supported`, `POST /transaction/{id}/cancel` (полный), `POST /transaction/{id}/cancel-partial` (заголовок `Idempotency-Key`, `{amount}`). Итог — callback CHARGEBACKED / PARTIALLY_REFUNDED. Баланс `GET /balance/all`.

Также есть платёжные ссылки `/v2/payment-links` (callback с `paymentLinkId`) и отдельный Payout API (HMAC-подпись).
Тестового режима и лимитов сумм в документации нет.
