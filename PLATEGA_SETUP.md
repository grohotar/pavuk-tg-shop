# Настройка Platega Payment Gateway

## Что было добавлено

Интеграция платежной системы Platega.io в ваш Telegram бот для приема платежей.

## Файлы, которые были изменены/созданы

1. **bot/services/platega_service.py** - новый сервис для работы с Platega API
2. **config/settings.py** - добавлены настройки Platega
3. **.env.example** - добавлены примеры переменных окружения
4. **bot/app/factories/build_services.py** - добавлена инициализация сервиса
5. **bot/app/web/web_server.py** - зарегистрирован webhook роут
6. **bot/main_bot.py** - добавлено закрытие сервиса при остановке
7. **bot/handlers/user/subscription/payments.py** - добавлен обработчик платежей
8. **bot/keyboards/inline/user_keyboards.py** - добавлена кнопка Platega
9. **locales/ru.json** и **locales/en.json** - добавлены переводы

## Настройка

### 1. Получите учетные данные Platega

Зарегистрируйтесь на https://platega.io и получите:
- **Merchant ID** (X-MerchantId)
- **Secret Key** (X-Secret)

### 2. Настройте переменные окружения

Добавьте в ваш `.env` файл:

```bash
# Platega Payment Gateway Configuration
PLATEGA_ENABLED=True                          # Включить Platega
PLATEGA_MERCHANT_ID=your_merchant_id          # Ваш Merchant ID
PLATEGA_SECRET_KEY=your_secret_key            # Ваш Secret Key
PLATEGA_PAYMENT_METHOD_ID=                    # Опционально: ID метода оплаты
```

### 3. Настройте Webhook в личном кабинете Platega

В настройках вашего аккаунта Platega укажите URL для callback:

```
https://ваш-домен.com/webhook/platega
```

Где `ваш-домен.com` - это значение вашей переменной `WEBHOOK_BASE_URL`.

### 4. Перезапустите бота

```bash
docker-compose down
docker-compose up -d
```

## Как это работает

1. **Создание платежа**: Пользователь выбирает Platega → создается запись в БД → запрос к Platega API → пользователь получает ссылку на оплату
2. **Webhook**: После оплаты Platega отправляет callback на `/webhook/platega` со статусом CONFIRMED или CANCELED
3. **Обработка**: Бот проверяет подпись, обновляет статус платежа, активирует подписку и отправляет уведомление пользователю

## API Endpoints Platega

- **POST /api/transactions** - создание платежа
- **GET /api/transactions/{id}** - проверка статуса
- **Webhook** - получение уведомлений о статусе

## Безопасность

- Все запросы к API авторизуются через заголовки `X-MerchantId` и `X-Secret`
- Webhook проверяет подлинность через те же заголовки
- Поддерживаются только статусы CONFIRMED (успешно) и CANCELED (отменено)

## Troubleshooting

### Платежи не создаются
- Проверьте правильность `PLATEGA_MERCHANT_ID` и `PLATEGA_SECRET_KEY`
- Убедитесь, что `PLATEGA_ENABLED=True`
- Проверьте логи: `docker logs remnawave-tg-shop`

### Webhook не работает
- Убедитесь, что URL webhook правильно настроен в личном кабинете Platega
- Проверьте, что `WEBHOOK_BASE_URL` указан корректно
- Webhook должен быть доступен извне (не localhost)

### Проверка логов
```bash
docker logs -f remnawave-tg-shop | grep -i platega
```
