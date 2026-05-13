#!/usr/bin/env python3
import asyncio
import signal
import sys
import threading
from datetime import datetime, timedelta
from loguru import logger
from config.settings import settings
from app.scanner.bybit_client import BybitP2PScanner
from app.analyzer.arbitrage import ArbitrageCalculator, VolumeAnalyzer
from app.bot.telegram import TelegramNotifier
from app.database.db_manager import DatabaseManager
from app.dashboard.server import app as dashboard_app
from app.nbu.limits import NBULimitManager
import uvicorn

# Налаштування логування
logger.remove()
logger.add(sys.stdout,
           format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
           level="INFO")
logger.add("logs/arbitrage_bot.log", rotation="1 day", retention="7 days", level="DEBUG")


class ArbitrageBot:
    def __init__(self):
        self.scanner = BybitP2PScanner()
        self.calculator = ArbitrageCalculator()
        self.notifier = TelegramNotifier()
        self.db = DatabaseManager()
        self.nbu = NBULimitManager()
        self.running = True
        self.last_alert_time = {}
        self.recent_opportunities = {}

    def is_duplicate_opportunity(self, buy_merchant: str, sell_merchant: str, buy_price: float, sell_price: float) -> bool:
        key = f"{buy_merchant}_{sell_merchant}_{buy_price:.2f}_{sell_price:.2f}"
        now = datetime.now()
        if key in self.recent_opportunities:
            last_seen = self.recent_opportunities[key]
            if now - last_seen < timedelta(minutes=30):
                logger.debug(f"Duplicate opportunity ignored: {key}")
                return True
        self.recent_opportunities[key] = now
        old_keys = [k for k, v in self.recent_opportunities.items() if now - v > timedelta(hours=1)]
        for k in old_keys:
            del self.recent_opportunities[k]
        return False

    async def process_opportunity(self, buy_offer: dict, sell_offer: dict):
        if self.is_duplicate_opportunity(
                buy_offer.get('merchant_name', 'Unknown'),
                sell_offer.get('merchant_name', 'Unknown'),
                buy_offer['price'],
                sell_offer['price']
        ):
            return

        max_uah = min(
            buy_offer.get('max_amount', float('inf')),
            sell_offer.get('max_amount', float('inf'))
        )
        min_uah = max(
            buy_offer.get('min_amount', 0),
            sell_offer.get('min_amount', 0)
        )
        allowed_min = max(min_uah, settings.MIN_DEAL_AMOUNT)
        if settings.MAX_DEAL_AMOUNT > 0:
            allowed_max = min(max_uah, settings.MAX_DEAL_AMOUNT, settings.STARTING_CAPITAL)
        else:
            allowed_max = min(max_uah, settings.STARTING_CAPITAL)

        if allowed_max < allowed_min:
            logger.warning(f"No suitable amount range: allowed [{allowed_min:.0f}-{allowed_max:.0f}] but need min {settings.MIN_DEAL_AMOUNT:.0f}")
            return

        optimal_capital = allowed_max
        logger.info(f"📊 Deal amount range: {allowed_min:.0f} - {allowed_max:.0f} UAH")
        logger.info(f"   Using capital: {optimal_capital:.0f} UAH")

        if not self.nbu.can_execute_deal(optimal_capital):
            remaining = self.nbu.get_remaining_limit()
            logger.warning(f"NBU limit insufficient: need {optimal_capital:.0f}, remaining {remaining:.0f}")
            return

        original_capital = self.calculator.capital
        self.calculator.capital = optimal_capital
        profit_data = self.calculator.calculate(
            buy_offer['price'],
            sell_offer['price'],
            buy_offer,
            sell_offer
        )
        self.calculator.capital = original_capital

        if not profit_data:
            logger.debug("Profit data is None - opportunity rejected by calculator")
            return

        profit_data['optimal_capital'] = optimal_capital
        profit_data['allowed_min'] = allowed_min
        profit_data['allowed_max'] = allowed_max

        logger.info(f"📊 OPPORTUNITY DETAILS:")
        logger.info(f"   Buy from: {profit_data['buy_merchant']} (rating: {profit_data['buy_completion_rate']}%, orders: {profit_data['buy_order_count']})")
        logger.info(f"   Sell to: {profit_data['sell_merchant']} (rating: {profit_data['sell_completion_rate']}%, orders: {profit_data['sell_order_count']})")
        logger.info(f"   Profit: +{profit_data['net_profit']:.2f} UAH, ROI: {profit_data['roi_percent']:.2f}%")

        if not VolumeAnalyzer.check_volume_limits(buy_offer, sell_offer, profit_data['usdt_amount']):
            logger.debug("Volume limits not satisfied")
            return

        opportunity_key = f"{profit_data['buy_merchant']}_{profit_data['sell_merchant']}_{profit_data['buy_price']:.2f}_{profit_data['sell_price']:.2f}"
        now = datetime.now().timestamp()

        if opportunity_key in self.last_alert_time:
            if now - self.last_alert_time[opportunity_key] < settings.COOLDOWN_SECONDS:
                logger.debug(f"Cooldown active for {opportunity_key}")
                return

        logger.success(f"✅ OPPORTUNITY FOUND! +{profit_data['net_profit']} UAH (ROI: {profit_data['roi_percent']}%)")
        self.db.save_opportunity(profit_data)

        if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_BOT_TOKEN != "your_bot_token_here":
            await self.notifier.send_opportunity(profit_data)
        else:
            print(f"\n🔔 OPPORTUNITY: +{profit_data['net_profit']} UAH | {profit_data['buy_merchant']} → {profit_data['sell_merchant']}\n")

        self.last_alert_time[opportunity_key] = now
        self.db.save_p2p_quotes('buy', [buy_offer])
        self.db.save_p2p_quotes('sell', [sell_offer])
        self.db.add_log("INFO", f"Opportunity found: +{profit_data['net_profit']:.2f} UAH | {profit_data['buy_merchant']} → {profit_data['sell_merchant']} | Spread: {profit_data['spread_percent']:.2f}%")

    async def scan_cycle(self):
        try:
            buy_offer, sell_offer = await self.scanner.get_best_offers()
            if not buy_offer or not sell_offer:
                logger.warning("Failed to get offers from Bybit")
                return
            spread = ((sell_offer['price'] - buy_offer['price']) / buy_offer['price']) * 100
            logger.info(f"📊 Market: Buy={buy_offer['price']:.2f} | Sell={sell_offer['price']:.2f} | Spread={spread:.2f}%")
            if sell_offer['price'] > buy_offer['price']:
                await self.process_opportunity(buy_offer, sell_offer)
        except Exception as e:
            logger.error(f"Error in scan cycle: {e}")
            self.db.add_log("ERROR", f"Scan cycle error: {str(e)}")

    async def run(self):
        logger.info(f"🚀 Starting P2P Arbitrage Bot")
        logger.info(f"💰 Capital: {settings.STARTING_CAPITAL} UAH")
        logger.info(f"⏱ Scan interval: {settings.SCAN_INTERVAL_SECONDS}s")
        logger.info(f"📈 Min spread: {settings.MIN_SPREAD_PERCENT}%")
        logger.info(f"🏦 NBU monthly limit: {settings.NBU_MONTHLY_LIMIT:,.0f} UAH")
        logger.info(f"📋 Min deal amount: {settings.MIN_DEAL_AMOUNT:.0f} UAH")
        logger.info(f"📋 Max deal amount: {settings.MAX_DEAL_AMOUNT if settings.MAX_DEAL_AMOUNT > 0 else '∞'} UAH")

        if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_BOT_TOKEN != "your_bot_token_here":
            await self.notifier.send_status(f"✅ Бот запущено")

        while self.running:
            await self.scan_cycle()
            await asyncio.sleep(settings.SCAN_INTERVAL_SECONDS)

    def stop(self):
        logger.info("Stopping bot...")
        self.running = False


def run_dashboard():
    """Запуск дашборду в окремому процесі"""
    uvicorn.run(dashboard_app, host="0.0.0.0", port=5002, log_level="warning")


def main():
    # Запускаємо дашборд в окремому потоці
    dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)
    dashboard_thread.start()
    logger.info(f"📊 Dashboard started on http://0.0.0.0:5002")

    # Запускаємо бота
    bot = ArbitrageBot()

    def signal_handler(signum, frame):
        logger.info(f"Stopping...")
        bot.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()