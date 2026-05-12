from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from loguru import logger
from config.settings import settings

Base = declarative_base()


class NBULimit(Base):
    __tablename__ = 'nbu_limits'

    id = Column(Integer, primary_key=True)
    total_limit = Column(Float, default=400000)
    used_amount = Column(Float, default=0)
    month = Column(String, default=lambda: datetime.now().strftime('%Y-%m'))
    updated_at = Column(DateTime, default=datetime.now)


class Transaction(Base):
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.now)
    amount_uah = Column(Float)
    amount_usdt = Column(Float)
    buy_merchant = Column(String)
    sell_merchant = Column(String)
    buy_price = Column(Float)
    sell_price = Column(Float)
    profit = Column(Float)
    status = Column(String, default='pending')  # pending, completed, cancelled


class NBULimitManager:
    def __init__(self):
        self.engine = create_engine(settings.DATABASE_URL)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self._init_limit()

    def _init_limit(self):
        """Ініціалізує ліміт на поточний місяць"""
        session = self.Session()
        try:
            current_month = datetime.now().strftime('%Y-%m')
            limit = session.query(NBULimit).filter(NBULimit.month == current_month).first()
            if not limit:
                limit = NBULimit(
                    total_limit=settings.NBU_MONTHLY_LIMIT,
                    used_amount=0,
                    month=current_month
                )
                session.add(limit)
                session.commit()
                logger.info(f"Created NBU limit for {current_month}: {settings.NBU_MONTHLY_LIMIT:,.0f} UAH")
        finally:
            session.close()

    def get_remaining_limit(self) -> float:
        """Отримати залишок ліміту"""
        session = self.Session()
        try:
            current_month = datetime.now().strftime('%Y-%m')
            limit = session.query(NBULimit).filter(NBULimit.month == current_month).first()
            if not limit:
                return settings.NBU_MONTHLY_LIMIT
            return limit.total_limit - limit.used_amount
        finally:
            session.close()

    def get_usage_percent(self) -> float:
        """Відсоток використання ліміту"""
        total = settings.NBU_MONTHLY_LIMIT
        remaining = self.get_remaining_limit()
        used = total - remaining
        return (used / total) * 100 if total > 0 else 0

    def get_used_amount(self) -> float:
        """Отримати використану суму"""
        session = self.Session()
        try:
            current_month = datetime.now().strftime('%Y-%m')
            limit = session.query(NBULimit).filter(NBULimit.month == current_month).first()
            if not limit:
                return 0
            return limit.used_amount
        finally:
            session.close()

    def can_execute_deal(self, amount_uah: float) -> bool:
        """Перевірити чи можна виконати угоду"""
        remaining = self.get_remaining_limit()
        return amount_uah <= remaining

    def reserve_limit(self, amount_uah: float) -> bool:
        """Зарезервувати ліміт"""
        session = self.Session()
        try:
            current_month = datetime.now().strftime('%Y-%m')
            limit = session.query(NBULimit).filter(NBULimit.month == current_month).first()

            if not limit:
                limit = NBULimit(
                    total_limit=settings.NBU_MONTHLY_LIMIT,
                    used_amount=0,
                    month=current_month
                )
                session.add(limit)

            if limit.used_amount + amount_uah > limit.total_limit:
                logger.warning(
                    f"NBU limit exceeded! Need {amount_uah:,.0f}, available {limit.total_limit - limit.used_amount:,.0f}")
                return False

            limit.used_amount += amount_uah
            limit.updated_at = datetime.now()
            session.commit()

            remaining = limit.total_limit - limit.used_amount
            logger.info(
                f"Reserved {amount_uah:,.0f} UAH. Used: {limit.used_amount:,.0f}/{limit.total_limit:,.0f} ({self.get_usage_percent():.1f}%)")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to reserve limit: {e}")
            return False
        finally:
            session.close()