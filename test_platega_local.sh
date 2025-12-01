#!/bin/bash

# Скрипт для локального тестирования Platega интеграции

echo "=== Platega Local Testing Setup ==="
echo ""

# Проверка наличия .env файла
if [ ! -f .env ]; then
    echo "❌ Файл .env не найден!"
    echo "Создайте .env файл на основе .env.example"
    exit 1
fi

# Проверка ngrok
if ! command -v ngrok &> /dev/null; then
    echo "❌ ngrok не установлен!"
    echo "Установите: brew install ngrok"
    exit 1
fi

echo "✅ Все зависимости установлены"
echo ""
echo "📝 Инструкция:"
echo "1. Запустите ngrok в отдельном терминале:"
echo "   ngrok http 8080"
echo ""
echo "2. Скопируйте HTTPS URL из ngrok (например: https://abc123.ngrok.io)"
echo ""
echo "3. Обновите .env файл:"
echo "   WEBHOOK_BASE_URL=https://abc123.ngrok.io"
echo "   PLATEGA_ENABLED=True"
echo "   PLATEGA_MERCHANT_ID=ваш_merchant_id"
echo "   PLATEGA_SECRET_KEY=ваш_secret_key"
echo ""
echo "4. Настройте webhook в личном кабинете Platega:"
echo "   https://abc123.ngrok.io/webhook/platega"
echo ""
echo "5. Запустите бота:"
echo "   python main.py"
echo ""
echo "6. Протестируйте платеж через бота"
echo ""
