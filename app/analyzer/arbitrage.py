from typing import Dict, Optional
from loguru import logger
from config.settings import settings


class ArbitrageCalculator:
    def __init__(self):
        self.capital = settings.STARTING_CAPITAL
        self.slippage = settings.SLIPPAGE_RESERVE_PERCENT / 100
        # Мінімальний спред залишаємо у відсотках (не ділимо на 100)
        self.min_spread_percent = settings.MIN_SPREAD_PERCENT

    def calculate(self, buy_price: float, sell_price: float, buy_offer: dict = None, sell_offer: dict = None) -> \
    Optional[Dict]:
        """
        Calculate arbitrage profit and ROI
        """
        if buy_price >= sell_price:
            return None

        # Розрахунок спреду у відсотках
        spread_raw = ((sell_price - buy_price) / buy_price) * 100

        # Перевірка мінімального спреду (правильне порівняння)
        if spread_raw < self.min_spread_percent:
            logger.debug(f"Spread {spread_raw:.2f}% < min {self.min_spread_percent}% - rejected")
            return None

        # Apply slippage to prices
        effective_buy = buy_price * (1 + self.slippage)
        effective_sell = sell_price * (1 - self.slippage)

        spread_with_slippage = ((effective_sell - effective_buy) / effective_buy) * 100

        # Перевірка з урахуванням прослизання
        if spread_with_slippage < self.min_spread_percent:
            logger.debug(
                f"Spread after slippage {spread_with_slippage:.2f}% < min {self.min_spread_percent}% - rejected")
            return None

        if effective_buy >= effective_sell:
            return None

        # Calculate USDT amount
        usdt_amount = self.capital / effective_buy
        revenue = usdt_amount * effective_sell
        gross_profit = revenue - self.capital
        fees = gross_profit * 0.001
        net_profit = gross_profit - fees

        if net_profit <= 0:
            return None

        roi = (net_profit / self.capital) * 100

        result = {
            'gross_profit': round(gross_profit, 2),
            'net_profit': round(net_profit, 2),
            'roi_percent': round(roi, 2),
            'spread_percent': round(spread_raw, 2),
            'spread_with_slippage': round(spread_with_slippage, 2),
            'usdt_amount': round(usdt_amount, 2),
            'buy_price': buy_price,
            'sell_price': sell_price,
            'effective_buy': round(effective_buy, 2),
            'effective_sell': round(effective_sell, 2),
            # Інформація про мерчантів
            'buy_merchant': buy_offer.get('merchant_name', 'Unknown') if buy_offer else 'Unknown',
            'sell_merchant': sell_offer.get('merchant_name', 'Unknown') if sell_offer else 'Unknown',
            'buy_completion_rate': buy_offer.get('completion_rate', 0) if buy_offer else 0,
            'sell_completion_rate': sell_offer.get('completion_rate', 0) if sell_offer else 0,
            'buy_order_count': buy_offer.get('order_count', 0) if buy_offer else 0,
            'sell_order_count': sell_offer.get('order_count', 0) if sell_offer else 0,
            'buy_min_amount': buy_offer.get('min_amount', 0) if buy_offer else 0,
            'buy_max_amount': buy_offer.get('max_amount', 0) if buy_offer else 0,
            'buy_available': buy_offer.get('available', 0) if buy_offer else 0,
            'sell_min_amount': sell_offer.get('min_amount', 0) if sell_offer else 0,
            'sell_max_amount': sell_offer.get('max_amount', 0) if sell_offer else 0,
            'sell_available': sell_offer.get('available', 0) if sell_offer else 0
        }

        return result


class VolumeAnalyzer:
    """Клас для перевірки об'ємів та лімітів"""

    @staticmethod
    def check_volume_limits(buy_offer: dict, sell_offer: dict, required_usdt: float) -> bool:
        """Check if both offers can handle the required volume"""

        required_uah = required_usdt * buy_offer.get('price', 0)

        # Перевіряємо ліміти покупця
        if required_uah < buy_offer.get('min_amount', 0):
            logger.debug(f"Required amount {required_uah:.0f} UAH below buy min {buy_offer.get('min_amount', 0):.0f}")
            return False

        if required_uah > buy_offer.get('max_amount', 0):
            logger.debug(f"Required amount {required_uah:.0f} UAH above buy max {buy_offer.get('max_amount', 0):.0f}")
            return False

        # Перевіряємо ліміти продавця
        if required_uah < sell_offer.get('min_amount', 0):
            logger.debug(f"Required amount {required_uah:.0f} UAH below sell min {sell_offer.get('min_amount', 0):.0f}")
            return False

        if required_uah > sell_offer.get('max_amount', 0):
            logger.debug(f"Required amount {required_uah:.0f} UAH above sell max {sell_offer.get('max_amount', 0):.0f}")
            return False

        # Перевіряємо доступний об'єм
        if required_usdt > buy_offer.get('available', 0):
            logger.debug(f"Required USDT {required_usdt:.0f} > available {buy_offer.get('available', 0):.0f}")
            return False

        if required_usdt > sell_offer.get('available', 0):
            logger.debug(f"Required USDT {required_usdt:.0f} > available {sell_offer.get('available', 0):.0f}")
            return False

        return True