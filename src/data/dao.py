"""
数据访问层 (DAO)
简化数据库操作
"""
import os
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from typing import List, Optional
from datetime import datetime

from .models import Trader, Trade, Position, CopyTrade

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/polymarket')

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


class TraderDAO:
    """交易者数据访问"""

    @staticmethod
    def save_trader(address: str, analysis: dict) -> Trader:
        """保存或更新交易者数据"""
        session = SessionLocal()
        try:
            trader = session.query(Trader).filter_by(address=address).first()
            if not trader:
                trader = Trader(address=address)

            trader.win_rate = analysis['win_rate']
            trader.total_markets = analysis['total_markets']
            trader.winning_markets = analysis['winning_markets']
            trader.losing_markets = analysis['losing_markets']
            trader.overall_pnl = analysis['overall_pnl']
            trader.total_wins = analysis['total_wins']
            trader.total_losses = analysis['total_losses']
            trader.profit_factor = analysis['profit_factor']
            trader.is_qualified = analysis.get('is_qualified', False)

            session.add(trader)
            session.commit()
            session.refresh(trader)
            return trader
        finally:
            session.close()

    @staticmethod
    def get_qualified_traders(min_win_rate: float = 0.90) -> List[Trader]:
        """获取合格的高胜率交易者"""
        session = SessionLocal()
        try:
            return session.query(Trader).filter(
                Trader.is_qualified == True,
                Trader.win_rate >= min_win_rate
            ).order_by(desc(Trader.win_rate)).all()
        finally:
            session.close()

    @staticmethod
    def get_trader(address: str) -> Optional[Trader]:
        """获取单个交易者"""
        session = SessionLocal()
        try:
            return session.query(Trader).filter_by(address=address).first()
        finally:
            session.close()


class TradeDAO:
    """交易记录数据访问"""

    @staticmethod
    def save_trades(trades: List[dict]):
        """批量保存交易记录"""
        session = SessionLocal()
        try:
            for trade_data in trades:
                trade = Trade(
                    trader_address=trade_data.get('trader_address'),
                    market_id=trade_data.get('market_id'),
                    side=trade_data.get('side'),
                    size=trade_data.get('size'),
                    price=trade_data.get('price'),
                    timestamp=trade_data.get('timestamp', datetime.utcnow())
                )
                session.add(trade)
            session.commit()
        finally:
            session.close()


class CopyTradeDAO:
    """跟单记录数据访问"""

    @staticmethod
    def save_copy_trade(copy_trade_data: dict) -> CopyTrade:
        """保存跟单记录"""
        session = SessionLocal()
        try:
            copy_trade = CopyTrade(**copy_trade_data)
            session.add(copy_trade)
            session.commit()
            session.refresh(copy_trade)
            return copy_trade
        finally:
            session.close()

    @staticmethod
    def get_recent_copy_trades(limit: int = 100) -> List[CopyTrade]:
        """获取最近的跟单记录"""
        session = SessionLocal()
        try:
            return session.query(CopyTrade).order_by(
                desc(CopyTrade.created_at)
            ).limit(limit).all()
        finally:
            session.close()
