from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class P2PQuote(Base):
    __tablename__ = 'p2p_quotes'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.now)
    order_type = Column(String)  # 'buy' or 'sell'
    price = Column(Float)
    min_amount = Column(Float)
    max_amount = Column(Float)
    available_amount = Column(Float)
    merchant_name = Column(String)
    completion_rate = Column(Float)
    order_count = Column(Integer)


class Opportunity(Base):
    __tablename__ = 'opportunities'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.now)
    buy_price = Column(Float)
    sell_price = Column(Float)
    spread_percent = Column(Float)
    gross_profit = Column(Float)
    net_profit = Column(Float)
    roi_percent = Column(Float)
    capital_used = Column(Float)
    usdt_amount = Column(Float)
    alert_sent = Column(Boolean, default=False)
    alert_time = Column(DateTime, nullable=True)
    # Дані мерчантів
    buy_merchant = Column(String, default='Unknown')
    sell_merchant = Column(String, default='Unknown')
    buy_completion_rate = Column(Float, default=0)
    sell_completion_rate = Column(Float, default=0)
    buy_order_count = Column(Integer, default=0)
    sell_order_count = Column(Integer, default=0)
    buy_min_amount = Column(Float, default=0)
    buy_max_amount = Column(Float, default=0)
    buy_available = Column(Float, default=0)
    sell_min_amount = Column(Float, default=0)
    sell_max_amount = Column(Float, default=0)
    sell_available = Column(Float, default=0)


class Log(Base):
    __tablename__ = 'logs'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.now)
    level = Column(String)  # INFO, SUCCESS, WARNING, ERROR
    message = Column(Text)


def init_database(db_url):
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return engine