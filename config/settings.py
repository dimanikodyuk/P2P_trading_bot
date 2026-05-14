import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env file
load_dotenv()


class Settings:
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

    # Database
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///p2p_arbitrage.db')

    # Trading settings
    STARTING_CAPITAL = float(os.getenv('STARTING_CAPITAL', 40000))
    MIN_SPREAD_PERCENT = float(os.getenv('MIN_SPREAD_PERCENT', 0.3))
    MIN_DEAL_AMOUNT = float(os.getenv('MIN_DEAL_AMOUNT', 20000))  # Мінімальна сума угоди
    MAX_DEAL_AMOUNT = float(os.getenv('MAX_DEAL_AMOUNT', 0))  # Максимальна сума (0 = без ліміту)
    SCAN_INTERVAL_SECONDS = int(os.getenv('SCAN_INTERVAL_SECONDS', 5))
    COOLDOWN_SECONDS = int(os.getenv('COOLDOWN_SECONDS', 30))
    SLIPPAGE_RESERVE_PERCENT = float(os.getenv('SLIPPAGE_RESERVE_PERCENT', 0.2))

    # Merchant filters
    MIN_COMPLETION_RATE = float(os.getenv('MIN_COMPLETION_RATE', 90))
    MIN_ORDERS_COUNT = int(os.getenv('MIN_ORDERS_COUNT', 50))

    MERCHANT_ONLINE_ONLY = os.getenv('MERCHANT_ONLINE_ONLY', 'true').lower() == 'true'

    # NBU limit
    NBU_MONTHLY_LIMIT = float(os.getenv('NBU_MONTHLY_LIMIT', 120000))

    # Dashboard
    DASHBOARD_PORT = int(os.getenv('DASHBOARD_PORT', 8000))
    DASHBOARD_HOST = os.getenv('DASHBOARD_HOST', '127.0.0.1')

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    # Bybit API
    BYBIT_P2P_URL = "https://api2.bybit.com/fiat/otc/item/online"


settings = Settings()