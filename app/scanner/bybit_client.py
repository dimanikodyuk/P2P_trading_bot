import aiohttp
import asyncio
from typing import List, Dict, Optional
from loguru import logger
from config.settings import settings


class BybitP2PScanner:
    def __init__(self):
        self.base_url = "https://api2.bybit.com/fiat/otc/item/online"
        self.headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
            'origin': 'https://www.bybit.com',
            'referer': 'https://www.bybit.com/fiat/trade/otc/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    async def fetch_quotes(self, side: str) -> List[Dict]:
        """
        Fetch P2P quotes from Bybit
        side: '0' for buy (купити USDT), '1' for sell (продати USDT)
        """
        # Правильний формат параметрів (як у тесті)
        payload = {
            "userId": "",  # Пустий рядок, не None
            "tokenId": "USDT",
            "currencyId": "UAH",
            "side": side,
            "paymentMethod": "Monobank",  # Рядок, не список
            "page": "1",  # Рядок
            "size": "50"  # Рядок
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                        self.base_url,
                        json=payload,
                        headers=self.headers,
                        timeout=aiohttp.ClientTimeout(total=10)
                ) as response:

                    if response.status != 200:
                        logger.error(f"HTTP {response.status} from Bybit API")
                        return []

                    data = await response.json()

                    # Перевіряємо код відповіді
                    if data.get('ret_code') != 0:
                        logger.error(f"Bybit API error: {data.get('ret_msg')}")
                        return []

                    # Отримуємо оголошення
                    result = data.get('result', {})
                    items = result.get('items', [])
                    total_count = result.get('count', 0)

                    logger.info(f"Found {len(items)} offers for side {side} (total: {total_count})")

                    quotes = []
                    filtered_by_limit = 0

                    for item in items:
                        merchant = item.get('merchantInfo', {})

                        # Якщо merchantInfo відсутній, використовуємо дані з item
                        if not merchant:
                            merchant = {
                                'merchantName': item.get('nickName', 'Unknown'),
                                'completionRate': item.get('completionRate', 95),
                                'totalOrderCount': item.get('totalOrderCount', 100)
                            }

                        price = float(item.get('price', 0))
                        min_amount = float(item.get('minAmount', 0))
                        max_amount = float(item.get('maxAmount', 0))
                        available = float(item.get('quantity', 0))

                        # Фільтруємо за мінімальним рейтингом (якщо налаштовано)
                        completion_rate = float(merchant.get('completionRate', 0))
                        order_count = int(merchant.get('totalOrderCount', 0))

                        if settings.MIN_COMPLETION_RATE > 0:
                            if completion_rate < settings.MIN_COMPLETION_RATE:
                                continue

                        if settings.MIN_ORDERS_COUNT > 0:
                            if order_count < settings.MIN_ORDERS_COUNT:
                                continue

                        # ===== НОВИЙ ФІЛЬТР: перевіряємо ліміт мерчанта =====
                        # Перевіряємо чи мерчант може працювати з нашою мінімальною сумою
                        if settings.MIN_DEAL_AMOUNT > 0:
                            if max_amount < settings.MIN_DEAL_AMOUNT:
                                filtered_by_limit += 1
                                continue

                        # Також перевіряємо чи мінімальний ліміт мерчанта не більший за наш капітал
                        if min_amount > settings.STARTING_CAPITAL:
                            filtered_by_limit += 1
                            continue

                        quote = {
                            'price': price,
                            'min_amount': min_amount,
                            'max_amount': max_amount,
                            'available': available,
                            'merchant_name': merchant.get('merchantName', 'Unknown'),
                            'completion_rate': completion_rate,
                            'order_count': order_count
                        }
                        quotes.append(quote)

                    # Сортуємо за ціною
                    if side == '0':  # Buy - найнижча ціна
                        quotes.sort(key=lambda x: x['price'])
                    else:  # Sell - найвища ціна
                        quotes.sort(key=lambda x: x['price'], reverse=True)

                    logger.info(
                        f"Filtered to {len(quotes)} offers for side {side} (skipped {filtered_by_limit} due to low limit < {settings.MIN_DEAL_AMOUNT} UAH)")

                    # Логуємо топ-5 пропозицій з їх лімітами
                    if quotes:
                        logger.info(f"Top 5 offers for side {side}:")
                        for i, q in enumerate(quotes[:5]):
                            logger.info(
                                f"   {i + 1}. {q['merchant_name']}: {q['price']} UAH (limit: {q['min_amount']:.0f}-{q['max_amount']:.0f} UAH)")

                    return quotes

        except asyncio.TimeoutError:
            logger.error("Timeout while fetching P2P data")
            return []
        except aiohttp.ClientError as e:
            logger.error(f"Client error: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return []

    async def get_best_offers(self):
        """Get best buy and sell offers"""
        # Отримуємо пропозиції на купівлю (найнижча ціна)
        buy_offers = await self.fetch_quotes('0')

        # Отримуємо пропозиції на продаж (найвища ціна)
        sell_offers = await self.fetch_quotes('1')

        if not buy_offers:
            logger.warning("No buy offers found (all filtered out due to limits?)")
            return None, None

        if not sell_offers:
            logger.warning("No sell offers found (all filtered out due to limits?)")
            return None, None

        # Найкраща пропозиція для купівлі (найнижча ціна)
        best_buy = buy_offers[0]

        # Найкраща пропозиція для продажу (найвища ціна)
        best_sell = sell_offers[0]

        logger.info(
            f"📈 Best BUY: {best_buy['price']} UAH from {best_buy['merchant_name']} (limit: {best_buy['min_amount']:.0f}-{best_buy['max_amount']:.0f} UAH, rating: {best_buy['completion_rate']}%, orders: {best_buy['order_count']})")
        logger.info(
            f"📉 Best SELL: {best_sell['price']} UAH from {best_sell['merchant_name']} (limit: {best_sell['min_amount']:.0f}-{best_sell['max_amount']:.0f} UAH, rating: {best_sell['completion_rate']}%, orders: {best_sell['order_count']})")

        return best_buy, best_sell