import asyncio
import aiohttp
import json


async def test_bybit_api():
    headers = {
        'accept': 'application/json, text/plain, */*',
        'content-type': 'application/json',
        'origin': 'https://www.bybit.com',
        'referer': 'https://www.bybit.com/fiat/trade/otc/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    # Правильний формат параметрів для Bybit API
    payloads_to_test = [
        # Варіант 1: всі параметри як рядки
        {
            "userId": "",
            "tokenId": "USDT",
            "currencyId": "UAH",
            "side": "0",
            "paymentMethod": "Monobank",
            "page": "1",
            "size": "10"
        },
        # Варіант 2: без userId
        {
            "tokenId": "USDT",
            "currencyId": "UAH",
            "side": "0",
            "paymentMethod": "Monobank",
            "page": 1,
            "size": 10
        },
        # Варіант 3: paymentMethod як список
        {
            "tokenId": "USDT",
            "currencyId": "UAH",
            "side": 0,
            "paymentMethod": ["Monobank"],
            "page": 1,
            "size": 10
        },
        # Варіант 4: API v5 формат
        {
            "category": "fiat",
            "tokenId": "USDT",
            "currencyId": "UAH",
            "side": "0",
            "paymentMethods": ["Monobank"],
            "page": 1,
            "limit": 10
        }
    ]

    for i, payload in enumerate(payloads_to_test, 1):
        print(f"\n{'=' * 50}")
        print(f"Testing payload {i}: {payload}")
        print('=' * 50)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                    "https://api2.bybit.com/fiat/otc/item/online",
                    json=payload,
                    headers=headers
            ) as resp:
                print(f"Status: {resp.status}")
                data = await resp.json()
                print(f"Response: {json.dumps(data, indent=2)[:500]}")

                if data.get('ret_code') == 0 or data.get('retCode') == 0:
                    items = data.get('result', {}).get('items', [])
                    print(f"✅ SUCCESS! Found {len(items)} items")
                    if items:
                        print(f"First item price: {items[0].get('price')}")
                        return items
                else:
                    print(f"❌ Error: {data.get('ret_msg', data.get('retMsg'))}")


if __name__ == "__main__":
    asyncio.run(test_bybit_api())