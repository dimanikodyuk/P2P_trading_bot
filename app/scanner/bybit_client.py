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
        payload = {
            "userId": "",
            "tokenId": "USDT",
            "currencyId": "UAH",
            "side": side,
            "paymentMethod": "Monobank (IBAN)",
            "page": "1",
            "size": "50"
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

                    if data.get('ret_code') != 0:
                        logger.error(f"Bybit API error: {data.get('ret_msg')}")
                        return []

                    result = data.get('result', {})
                    items = result.get('items', [])
                    total_count = result.get('count', 0)

                    logger.info(f"Found {len(items)} offers for side {side} (total: {total_count})")

                    quotes = []
                    filtered_by_limit = 0
                    filtered_by_status = 0

                    for item in items:
                        merchant = item.get('merchantInfo', {})

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

                        # ===== ДОДАТКОВА ІНФОРМАЦІЯ =====
                        # Кількість угод мерчанта
                        order_count = int(merchant.get('totalOrderCount', 0))

                        # Рейтинг завершення
                        completion_rate = float(merchant.get('completionRate', 0))

                        # Рекомендація (найкращий вибір)
                        is_recommended = item.get('isRecommended', False)

                        # Платіжні методи (IBAN, Visa, Mastercard)
                        payment_methods = []
                        if 'paymentMethod' in item:
                            payment_methods = [item['paymentMethod']]
                        elif 'paymentMethods' in item:
                            payment_methods = item['paymentMethods']

                        # Статус онлайн
                        merchant_status = self._parse_merchant_status(merchant, item)

                        # Фільтр за статусом
                        if settings.MERCHANT_ONLINE_ONLY:
                            if merchant_status != 'online':
                                filtered_by_status += 1
                                continue

                        # Фільтри рейтингу та кількості угод
                        if settings.MIN_COMPLETION_RATE > 0:
                            if completion_rate < settings.MIN_COMPLETION_RATE:
                                continue

                        if settings.MIN_ORDERS_COUNT > 0:
                            if order_count < settings.MIN_ORDERS_COUNT:
                                continue

                        # Фільтр за лімітом суми
                        if settings.MIN_DEAL_AMOUNT > 0:
                            if max_amount < settings.MIN_DEAL_AMOUNT:
                                filtered_by_limit += 1
                                continue

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
                            'order_count': order_count,
                            'status': merchant_status,
                            # Нова інформація
                            'is_recommended': is_recommended,
                            'payment_methods': payment_methods,
                            'avatar': merchant.get('avatar', ''),
                            'merchant_id': merchant.get('merchantId', ''),
                            'user_no': merchant.get('userNo', '')
                        }
                        quotes.append(quote)

                    # Сортування за ціною
                    if side == '0':
                        quotes.sort(key=lambda x: x['price'])
                    else:
                        quotes.sort(key=lambda x: x['price'], reverse=True)

                    logger.info(
                        f"Filtered to {len(quotes)} offers for side {side} "
                        f"(skipped {filtered_by_limit} by limit, {filtered_by_status} by status)")

                    if quotes:
                        logger.info(f"Top 5 offers for side {side}:")
                        for i, q in enumerate(quotes[:5]):
                            status_emoji = "🟢" if q['status'] == 'online' else (
                                "🔴" if q['status'] == 'offline' else "⚪")
                            rec_text = "⭐" if q['is_recommended'] else ""
                            logger.info(
                                f"   {i + 1}. {status_emoji} {rec_text} {q['merchant_name']}: {q['price']} UAH "
                                f"(limit: {q['min_amount']:.0f}-{q['max_amount']:.0f} UAH, orders: {q['order_count']}, "
                                f"rating: {q['completion_rate']}%, status: {q['status']})")

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

    def _parse_merchant_status(self, merchant: dict, item: dict) -> str:
        """Парсинг статусу мерчанта (online/offline)"""
        merchant_status = 'unknown'

        if 'isOnline' in merchant:
            merchant_status = 'online' if merchant.get('isOnline') else 'offline'
        elif 'online' in merchant:
            merchant_status = 'online' if merchant.get('online') else 'offline'
        elif 'status' in merchant:
            merchant_status = merchant.get('status', 'unknown')
            if merchant_status == '1' or merchant_status == 'online':
                merchant_status = 'online'
            elif merchant_status == '0' or merchant_status == 'offline':
                merchant_status = 'offline'
        elif 'isActive' in merchant:
            merchant_status = 'online' if merchant.get('isActive') else 'offline'

        if merchant_status == 'unknown':
            if 'isOnline' in item:
                merchant_status = 'online' if item.get('isOnline') else 'offline'
            elif 'online' in item:
                merchant_status = 'online' if item.get('online') else 'offline'

        return merchant_status

    async def get_best_offers(self):
        """Get best buy and sell offers"""
        buy_offers = await self.fetch_quotes('0')
        sell_offers = await self.fetch_quotes('1')

        if not buy_offers:
            logger.warning("No buy offers found (all filtered out due to limits?)")
            return None, None

        if not sell_offers:
            logger.warning("No sell offers found (all filtered out due to limits?)")
            return None, None

        best_buy = buy_offers[0]
        best_sell = sell_offers[0]

        status_buy_emoji = "🟢" if best_buy['status'] == 'online' else ("🔴" if best_buy['status'] == 'offline' else "⚪")
        status_sell_emoji = "🟢" if best_sell['status'] == 'online' else (
            "🔴" if best_sell['status'] == 'offline' else "⚪")
        rec_buy = "⭐ " if best_buy.get('is_recommended') else ""
        rec_sell = "⭐ " if best_sell.get('is_recommended') else ""

        logger.info(
            f"📈 Best BUY: {status_buy_emoji} {rec_buy}{best_buy['price']} UAH from {best_buy['merchant_name']} "
            f"(limit: {best_buy['min_amount']:.0f}-{best_buy['max_amount']:.0f} UAH, "
            f"orders: {best_buy['order_count']}, rating: {best_buy['completion_rate']}%, status: {best_buy['status']})")
        logger.info(
            f"📉 Best SELL: {status_sell_emoji} {rec_sell}{best_sell['price']} UAH from {best_sell['merchant_name']} "
            f"(limit: {best_sell['min_amount']:.0f}-{best_sell['max_amount']:.0f} UAH, "
            f"orders: {best_sell['order_count']}, rating: {best_sell['completion_rate']}%, status: {best_sell['status']})")

        return best_buy, best_sell