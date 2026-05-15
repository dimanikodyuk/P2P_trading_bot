from sqlalchemy import create_engine, desc, func
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from loguru import logger
from .models import Base, P2PQuote, Opportunity, Log
from config.settings import settings


class DatabaseManager:
    def __init__(self):
        self.engine = create_engine(settings.DATABASE_URL)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def save_p2p_quotes(self, order_type: str, quotes: List[Dict]):
        """Save P2P quotes to database"""
        session = self.Session()
        try:
            for quote in quotes:
                p2p_quote = P2PQuote(
                    order_type=order_type,
                    price=quote['price'],
                    min_amount=quote['min_amount'],
                    max_amount=quote['max_amount'],
                    available_amount=quote['available'],
                    merchant_name=quote['merchant_name'],
                    completion_rate=quote['completion_rate'],
                    order_count=quote['order_count']
                )
                session.add(p2p_quote)
            session.commit()
            logger.debug(f"Saved {len(quotes)} {order_type} quotes")
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save quotes: {e}")
        finally:
            session.close()

    def save_opportunity(self, profit_data: Dict) -> int:
        """Save arbitrage opportunity with merchant details"""
        session = self.Session()
        try:
            opp = Opportunity(
                buy_price=profit_data['buy_price'],
                sell_price=profit_data['sell_price'],
                spread_percent=profit_data['spread_percent'],
                gross_profit=profit_data['gross_profit'],
                net_profit=profit_data['net_profit'],
                roi_percent=profit_data['roi_percent'],
                capital_used=profit_data.get('optimal_capital', settings.STARTING_CAPITAL),
                usdt_amount=profit_data['usdt_amount'],
                alert_sent=False,
                # Дані мерчантів
                buy_merchant=profit_data.get('buy_merchant', 'Unknown'),
                sell_merchant=profit_data.get('sell_merchant', 'Unknown'),
                buy_completion_rate=profit_data.get('buy_completion_rate', 0),
                sell_completion_rate=profit_data.get('sell_completion_rate', 0),
                buy_order_count=profit_data.get('buy_order_count', 0),
                sell_order_count=profit_data.get('sell_order_count', 0),
                buy_min_amount=profit_data.get('buy_min_amount', 0),
                buy_max_amount=profit_data.get('buy_max_amount', 0),
                buy_available=profit_data.get('buy_available', 0),
                sell_min_amount=profit_data.get('sell_min_amount', 0),
                sell_max_amount=profit_data.get('sell_max_amount', 0),
                sell_available=profit_data.get('sell_available', 0),
                buy_status=profit_data.get('buy_status', 'unknown'),
                sell_status=profit_data.get('sell_status', 'unknown'),
                buy_is_recommended=profit_data.get('buy_is_recommended', False),
                sell_is_recommended=profit_data.get('sell_is_recommended', False)
            )
            session.add(opp)
            session.commit()

            self.add_log("INFO", f"New opportunity #{opp.id}: +{profit_data['net_profit']:.2f} UAH, spread {profit_data['spread_percent']:.2f}%")
            logger.info(f"Saved opportunity #{opp.id} with profit {profit_data['net_profit']} UAH")
            return opp.id
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save opportunity: {e}")
            return 0
        finally:
            session.close()

    def is_duplicate_opportunity(self, buy_merchant: str, sell_merchant: str, buy_price: float, sell_price: float, minutes: int = 30) -> bool:
        """Перевірити чи була така ж можливість за останні N хвилин"""
        session = self.Session()
        try:
            since = datetime.now() - timedelta(minutes=minutes)
            exists = session.query(Opportunity).filter(
                Opportunity.buy_merchant == buy_merchant,
                Opportunity.sell_merchant == sell_merchant,
                Opportunity.buy_price == buy_price,
                Opportunity.sell_price == sell_price,
                Opportunity.timestamp >= since
            ).first() is not None
            return exists
        except Exception as e:
            logger.error(f"Failed to check duplicate: {e}")
            return False
        finally:
            session.close()

    def get_recent_opportunities(self, hours: int = 24) -> List[Dict]:
        """Get recent opportunities for dashboard"""
        session = self.Session()
        try:
            since = datetime.now() - timedelta(hours=hours)
            opportunities = session.query(Opportunity).filter(
                Opportunity.timestamp >= since
            ).order_by(desc(Opportunity.timestamp)).limit(100).all()

            return [
                {
                    'id': opp.id,
                    'timestamp': opp.timestamp.isoformat(),
                    'spread': opp.spread_percent,
                    'profit': opp.net_profit,
                    'roi': opp.roi_percent,
                    'buy_price': opp.buy_price,
                    'sell_price': opp.sell_price,
                    'usdt_amount': opp.usdt_amount,
                    'buy_merchant': opp.buy_merchant,
                    'sell_merchant': opp.sell_merchant,
                    'alert_sent': opp.alert_sent
                }
                for opp in opportunities
            ]
        except Exception as e:
            logger.error(f"Failed to get opportunities: {e}")
            return []
        finally:
            session.close()

    def get_statistics(self) -> Dict:
        """Get statistics for dashboard"""
        session = self.Session()
        try:
            since = datetime.now() - timedelta(hours=24)
            opportunities = session.query(Opportunity).filter(
                Opportunity.timestamp >= since,
                Opportunity.alert_sent == True
            ).all()

            if not opportunities:
                return {
                    'total_opportunities': 0,
                    'avg_profit': 0,
                    'max_profit': 0,
                    'total_profit': 0,
                    'avg_spread': 0,
                    'success_rate': 0
                }

            total_profit = sum(opp.net_profit for opp in opportunities)
            avg_profit = total_profit / len(opportunities)
            max_profit = max(opp.net_profit for opp in opportunities)
            avg_spread = sum(opp.spread_percent for opp in opportunities) / len(opportunities)

            return {
                'total_opportunities': len(opportunities),
                'avg_profit': round(avg_profit, 2),
                'max_profit': round(max_profit, 2),
                'total_profit': round(total_profit, 2),
                'avg_spread': round(avg_spread, 2),
                'success_rate': 100.0
            }
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {
                'total_opportunities': 0,
                'avg_profit': 0,
                'max_profit': 0,
                'total_profit': 0,
                'avg_spread': 0,
                'success_rate': 0
            }
        finally:
            session.close()

    def get_latest_quotes(self) -> Dict:
        """Get latest market quotes"""
        session = self.Session()
        try:
            latest_buy = session.query(P2PQuote).filter(
                P2PQuote.order_type == 'buy'
            ).order_by(desc(P2PQuote.timestamp)).first()

            latest_sell = session.query(P2PQuote).filter(
                P2PQuote.order_type == 'sell'
            ).order_by(desc(P2PQuote.timestamp)).first()

            return {
                'buy_price': latest_buy.price if latest_buy else None,
                'sell_price': latest_sell.price if latest_sell else None,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get latest quotes: {e}")
            return {'buy_price': None, 'sell_price': None}
        finally:
            session.close()

    def get_top_merchants(self, limit: int = 10) -> List[Dict]:
        """Get top merchants by volume"""
        session = self.Session()
        try:
            merchants = session.query(
                P2PQuote.merchant_name,
                func.count(P2PQuote.id).label('orders'),
                func.avg(P2PQuote.price).label('avg_price')
            ).group_by(P2PQuote.merchant_name).order_by(
                desc('orders')
            ).limit(limit).all()

            return [
                {
                    'name': m.merchant_name,
                    'orders': m.orders,
                    'avg_price': round(m.avg_price, 2)
                }
                for m in merchants
            ]
        except Exception as e:
            logger.error(f"Failed to get top merchants: {e}")
            return []
        finally:
            session.close()

    def get_spread_history(self, hours: int = 24) -> List[Dict]:
        """Get spread history for chart"""
        session = self.Session()
        try:
            since = datetime.now() - timedelta(hours=hours)
            opportunities = session.query(Opportunity).filter(
                Opportunity.timestamp >= since,
                Opportunity.alert_sent == True
            ).order_by(Opportunity.timestamp).all()

            return [
                {
                    'timestamp': opp.timestamp.isoformat(),
                    'spread': opp.spread_percent,
                    'profit': opp.net_profit
                }
                for opp in opportunities
            ]
        except Exception as e:
            logger.error(f"Failed to get spread history: {e}")
            return []
        finally:
            session.close()

    def add_log(self, level: str, message: str):
        """Add log entry to database"""
        session = self.Session()
        try:
            log = Log(level=level.upper(), message=message)
            session.add(log)
            session.commit()
        except Exception as e:
            logger.error(f"Failed to add log: {e}")
        finally:
            session.close()

    def get_heatmap_data(self, days: int = 30, type: str = "all") -> Dict:
        """Отримати дані для теплової карти прибутку по годинах та днях"""
        session = self.Session()
        try:
            since = datetime.now() - timedelta(days=days)

            # Фільтр за типом угод
            if type == "confirmed":
                # Тільки підтверджені угоди
                opportunities = session.query(Opportunity).filter(
                    Opportunity.timestamp >= since,
                    Opportunity.alert_sent == True
                ).all()
            else:
                # Всі можливості
                opportunities = session.query(Opportunity).filter(
                    Opportunity.timestamp >= since
                ).all()

            # Підготовка даних: [день_тижня][година] = сума_прибутку
            heatmap_data = [[0] * 24 for _ in range(7)]
            counts = [[0] * 24 for _ in range(7)]
            days_map = ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'НД']

            for opp in opportunities:
                try:
                    weekday = opp.timestamp.weekday()
                    hour = opp.timestamp.hour
                    profit = opp.net_profit if opp.net_profit else 0

                    if profit > 0:
                        heatmap_data[weekday][hour] += profit
                        counts[weekday][hour] += 1
                except Exception as e:
                    logger.error(f"Error processing opportunity {opp.id}: {e}")
                    continue

            # Розраховуємо середній прибуток
            avg_profit = [[0] * 24 for _ in range(7)]
            for w in range(7):
                for h in range(24):
                    if counts[w][h] > 0:
                        avg_profit[w][h] = round(heatmap_data[w][h] / counts[w][h], 2)

            return {
                'days': days_map,
                'hours': list(range(24)),
                'data': avg_profit,
                'counts': counts
            }
        except Exception as e:
            logger.error(f"Failed to get heatmap data: {e}")
            return {
                'days': ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'НД'],
                'hours': list(range(24)),
                'data': [[0] * 24 for _ in range(7)],
                'counts': [[0] * 24 for _ in range(7)]
            }
        finally:
            session.close()

    def get_logs(self, limit: int = 200) -> List[Dict]:
        """Get recent logs"""
        session = self.Session()
        try:
            logs = session.query(Log).order_by(desc(Log.timestamp)).limit(limit).all()
            return [
                {
                    'timestamp': log.timestamp.isoformat(),
                    'level': log.level,
                    'message': log.message
                }
                for log in logs
            ]
        except Exception as e:
            logger.error(f"Failed to get logs: {e}")
            return []
        finally:
            session.close()