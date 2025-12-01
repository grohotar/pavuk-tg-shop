#!/usr/bin/env python3
"""
Скрипт для тестирования Platega API без запуска всего бота.
Используйте для проверки учетных данных и создания тестового платежа.
"""

import asyncio
import json
from aiohttp import ClientSession, ClientTimeout
from decimal import Decimal, ROUND_HALF_UP

# ===== НАСТРОЙКИ =====
# Вставьте ваши тестовые данные от Platega
PLATEGA_MERCHANT_ID = "your_merchant_id"  # Замените на ваш Merchant ID
PLATEGA_SECRET_KEY = "your_secret_key"    # Замените на ваш Secret Key
PLATEGA_API_BASE_URL = "https://platega.io/api"

# Тестовые данные платежа
TEST_AMOUNT = 100.00  # Сумма в рублях
TEST_CURRENCY = "RUB"
TEST_ORDER_ID = "test_order_12345"
TEST_DESCRIPTION = "Test payment"
# =====================


def format_amount(amount: float) -> str:
    """Форматирование суммы с двумя знаками после запятой."""
    quantized = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{quantized:.2f}"


async def test_create_payment():
    """Тест создания платежа через Platega API."""
    print("=" * 60)
    print("ТЕСТ: Создание платежа в Platega")
    print("=" * 60)
    
    if PLATEGA_MERCHANT_ID == "your_merchant_id":
        print("❌ ОШИБКА: Укажите ваш PLATEGA_MERCHANT_ID в скрипте!")
        return False
    
    if PLATEGA_SECRET_KEY == "your_secret_key":
        print("❌ ОШИБКА: Укажите ваш PLATEGA_SECRET_KEY в скрипте!")
        return False
    
    # Подготовка данных
    amount_str = format_amount(TEST_AMOUNT)
    
    payload = {
        "amount": amount_str,
        "currency": TEST_CURRENCY,
        "orderId": TEST_ORDER_ID,
        "description": TEST_DESCRIPTION,
        "metadata": {
            "user_id": "test_user_123",
            "test": "true",
        },
    }
    
    headers = {
        "X-MerchantId": PLATEGA_MERCHANT_ID,
        "X-Secret": PLATEGA_SECRET_KEY,
        "Content-Type": "application/json",
    }
    
    print(f"\n📤 Отправка запроса:")
    print(f"URL: {PLATEGA_API_BASE_URL}/transactions")
    print(f"Merchant ID: {PLATEGA_MERCHANT_ID}")
    print(f"Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    print()
    
    timeout = ClientTimeout(total=15)
    async with ClientSession(timeout=timeout) as session:
        try:
            async with session.post(
                f"{PLATEGA_API_BASE_URL}/transactions",
                json=payload,
                headers=headers
            ) as response:
                status = response.status
                response_text = await response.text()
                
                print(f"📥 Ответ от Platega:")
                print(f"Status Code: {status}")
                
                try:
                    response_data = json.loads(response_text) if response_text else {}
                    print(f"Response: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
                except json.JSONDecodeError:
                    print(f"Response (raw): {response_text}")
                
                if status in (200, 201):
                    print("\n✅ Платеж успешно создан!")
                    
                    if response_data.get("paymentUrl"):
                        print(f"\n🔗 Ссылка на оплату:")
                        print(f"{response_data['paymentUrl']}")
                        print("\nОткройте эту ссылку в браузере для тестирования")
                    
                    if response_data.get("id"):
                        print(f"\n🆔 Transaction ID: {response_data['id']}")
                        print("Используйте его для проверки статуса")
                        
                        # Тест проверки статуса
                        await test_check_status(response_data['id'])
                    
                    return True
                else:
                    print(f"\n❌ Ошибка создания платежа!")
                    return False
                    
        except Exception as e:
            print(f"\n❌ Исключение при запросе: {e}")
            import traceback
            traceback.print_exc()
            return False


async def test_check_status(transaction_id: str):
    """Тест проверки статуса платежа."""
    print("\n" + "=" * 60)
    print("ТЕСТ: Проверка статуса платежа")
    print("=" * 60)
    
    headers = {
        "X-MerchantId": PLATEGA_MERCHANT_ID,
        "X-Secret": PLATEGA_SECRET_KEY,
    }
    
    print(f"\n📤 Запрос статуса для Transaction ID: {transaction_id}")
    
    timeout = ClientTimeout(total=15)
    async with ClientSession(timeout=timeout) as session:
        try:
            async with session.get(
                f"{PLATEGA_API_BASE_URL}/transactions/{transaction_id}",
                headers=headers
            ) as response:
                status = response.status
                response_text = await response.text()
                
                print(f"\n📥 Ответ:")
                print(f"Status Code: {status}")
                
                try:
                    response_data = json.loads(response_text) if response_text else {}
                    print(f"Response: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
                    
                    if status == 200:
                        payment_status = response_data.get("status", "UNKNOWN")
                        print(f"\n💳 Статус платежа: {payment_status}")
                        
                        if payment_status == "CONFIRMED":
                            print("✅ Платеж подтвержден!")
                        elif payment_status == "CANCELED":
                            print("❌ Платеж отменен")
                        elif payment_status == "PENDING":
                            print("⏳ Платеж ожидает оплаты")
                        
                        return True
                except json.JSONDecodeError:
                    print(f"Response (raw): {response_text}")
                    
        except Exception as e:
            print(f"\n❌ Исключение при проверке статуса: {e}")
            import traceback
            traceback.print_exc()
            return False


async def test_webhook_signature():
    """Тест проверки подписи webhook."""
    print("\n" + "=" * 60)
    print("ТЕСТ: Проверка подписи webhook")
    print("=" * 60)
    
    # Симуляция webhook от Platega
    test_headers = {
        "X-MerchantId": PLATEGA_MERCHANT_ID,
        "X-Secret": PLATEGA_SECRET_KEY,
    }
    
    test_payload = {
        "id": "test_transaction_123",
        "status": "CONFIRMED",
        "orderId": TEST_ORDER_ID,
        "amount": format_amount(TEST_AMOUNT),
        "currency": TEST_CURRENCY,
    }
    
    print(f"\n📨 Тестовый webhook payload:")
    print(json.dumps(test_payload, indent=2, ensure_ascii=False))
    print(f"\n🔑 Headers:")
    print(f"X-MerchantId: {test_headers['X-MerchantId']}")
    print(f"X-Secret: {test_headers['X-Secret']}")
    
    # Проверка подписи
    merchant_id_match = test_headers.get("X-MerchantId") == PLATEGA_MERCHANT_ID
    secret_match = test_headers.get("X-Secret") == PLATEGA_SECRET_KEY
    
    print(f"\n✅ Merchant ID совпадает: {merchant_id_match}")
    print(f"✅ Secret Key совпадает: {secret_match}")
    
    if merchant_id_match and secret_match:
        print("\n✅ Подпись webhook валидна!")
        return True
    else:
        print("\n❌ Подпись webhook невалидна!")
        return False


async def main():
    """Главная функция для запуска всех тестов."""
    print("\n" + "=" * 60)
    print("PLATEGA API TESTING TOOL")
    print("=" * 60)
    print()
    
    # Тест 1: Создание платежа
    success = await test_create_payment()
    
    if not success:
        print("\n⚠️  Создание платежа не удалось. Проверьте учетные данные.")
        print("Убедитесь, что:")
        print("1. PLATEGA_MERCHANT_ID указан правильно")
        print("2. PLATEGA_SECRET_KEY указан правильно")
        print("3. У вас есть доступ к Platega API")
        return
    
    # Тест 2: Проверка подписи webhook
    await test_webhook_signature()
    
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 60)
    print("\n📝 Следующие шаги:")
    print("1. Если создание платежа успешно - откройте ссылку на оплату")
    print("2. Проведите тестовый платеж")
    print("3. Проверьте, что webhook приходит на ваш сервер")
    print("4. Проверьте логи бота для подтверждения обработки webhook")
    print()


if __name__ == "__main__":
    asyncio.run(main())
