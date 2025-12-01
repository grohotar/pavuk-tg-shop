# Локальное тестирование Platega интеграции

## Вариант 1: Тестирование API без запуска бота

Самый простой способ проверить учетные данные и API:

### Шаг 1: Настройте тестовый скрипт

Откройте `test_platega_api.py` и укажите ваши тестовые данные:

```python
PLATEGA_MERCHANT_ID = "ваш_merchant_id"
PLATEGA_SECRET_KEY = "ваш_secret_key"
```

### Шаг 2: Запустите тест

```bash
python test_platega_api.py
```

Скрипт проверит:
- ✅ Создание платежа через API
- ✅ Получение ссылки на оплату
- ✅ Проверку статуса платежа
- ✅ Валидацию подписи webhook

---

## Вариант 2: Полное тестирование с ботом (локально)

Для тестирования webhook и полного flow:

### Шаг 1: Установите ngrok

```bash
# macOS
brew install ngrok

# Или скачайте с https://ngrok.com/download
```

### Шаг 2: Запустите ngrok

В отдельном терминале:

```bash
ngrok http 8080
```

Вы увидите что-то вроде:
```
Forwarding  https://abc123.ngrok.io -> http://localhost:8080
```

Скопируйте HTTPS URL (например: `https://abc123.ngrok.io`)

### Шаг 3: Настройте .env

Создайте `.env` файл (если еще нет) и добавьте:

```bash
# Telegram
BOT_TOKEN=ваш_токен_бота
ADMIN_IDS=ваш_telegram_id

# Database (для локального тестирования можно использовать SQLite или локальный PostgreSQL)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=vpn_shop_test

# Webhook (используйте URL от ngrok)
WEBHOOK_BASE_URL=https://abc123.ngrok.io

# Platega (ваши тестовые данные)
PLATEGA_ENABLED=True
PLATEGA_MERCHANT_ID=ваш_merchant_id
PLATEGA_SECRET_KEY=ваш_secret_key

# Другие настройки
DEFAULT_LANGUAGE=ru
DEFAULT_CURRENCY_SYMBOL=RUB

# Отключите другие платежные системы для чистоты теста
YOOKASSA_ENABLED=False
FREEKASSA_ENABLED=False
STARS_ENABLED=False
TRIBUTE_ENABLED=False
CRYPTOPAY_ENABLED=False

# Настройки подписки
1_MONTH_ENABLED=True
RUB_PRICE_1_MONTH=100
```

### Шаг 4: Настройте webhook в Platega

Зайдите в личный кабинет Platega и укажите URL для callback:

```
https://abc123.ngrok.io/webhook/platega
```

⚠️ **Важно**: Используйте HTTPS URL от ngrok, а не HTTP!

### Шаг 5: Запустите базу данных (если нужно)

Если используете Docker для PostgreSQL:

```bash
docker run -d \
  --name platega-test-db \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=vpn_shop_test \
  -p 5432:5432 \
  postgres:17
```

### Шаг 6: Запустите бота

```bash
python main.py
```

### Шаг 7: Протестируйте

1. Откройте бота в Telegram
2. Нажмите `/start`
3. Выберите "🚀 Купить"
4. Выберите период подписки
5. Выберите "💳 Platega"
6. Получите ссылку на оплату
7. Откройте ссылку и проведите тестовый платеж

### Шаг 8: Проверьте логи

В терминале с ботом вы должны увидеть:

```
INFO - Platega webhook route configured at: [POST] /webhook/platega
INFO - AIOHTTP server started on http://0.0.0.0:8080
```

После оплаты:
```
INFO - Platega webhook: payment X succeeded
INFO - Subscription activated for user Y
```

---

## Вариант 3: Тестирование webhook вручную

Если хотите протестировать только обработку webhook:

### Создайте тестовый скрипт

```bash
# test_webhook.sh
curl -X POST http://localhost:8080/webhook/platega \
  -H "Content-Type: application/json" \
  -H "X-MerchantId: ваш_merchant_id" \
  -H "X-Secret: ваш_secret_key" \
  -d '{
    "id": "test_transaction_123",
    "status": "CONFIRMED",
    "orderId": "1",
    "amount": "100.00",
    "currency": "RUB"
  }'
```

⚠️ **Важно**: 
- `orderId` должен соответствовать существующему `payment_id` в вашей БД
- Сначала создайте платеж через бота, затем отправьте webhook

---

## Отладка

### Проблема: Webhook не приходит

1. Проверьте, что ngrok запущен и URL правильный
2. Проверьте, что webhook URL настроен в Platega
3. Проверьте логи ngrok: `http://localhost:4040` (Web Interface)

### Проблема: Ошибка авторизации API

1. Проверьте `PLATEGA_MERCHANT_ID` и `PLATEGA_SECRET_KEY`
2. Убедитесь, что используете тестовые данные для тестовой среды
3. Проверьте, что у вас есть доступ к API

### Проблема: База данных

```bash
# Проверка подключения к PostgreSQL
psql -h localhost -U postgres -d vpn_shop_test

# Проверка таблицы платежей
SELECT * FROM payments ORDER BY created_at DESC LIMIT 5;
```

### Просмотр логов в реальном времени

```bash
# Фильтр только Platega
python main.py 2>&1 | grep -i platega

# Все логи
python main.py
```

---

## Чек-лист перед тестированием

- [ ] ngrok установлен и запущен
- [ ] `.env` файл настроен с правильными данными
- [ ] `WEBHOOK_BASE_URL` указывает на ngrok URL
- [ ] `PLATEGA_ENABLED=True`
- [ ] Webhook URL настроен в личном кабинете Platega
- [ ] База данных запущена и доступна
- [ ] Бот запущен без ошибок
- [ ] В логах видно "Platega webhook route configured"

---

## Полезные команды

```bash
# Проверка портов
lsof -i :8080

# Остановка ngrok
pkill ngrok

# Очистка тестовых данных из БД
psql -h localhost -U postgres -d vpn_shop_test -c "DELETE FROM payments WHERE provider='platega';"

# Просмотр последних платежей
psql -h localhost -U postgres -d vpn_shop_test -c "SELECT payment_id, user_id, amount, status, provider FROM payments ORDER BY created_at DESC LIMIT 10;"
```
