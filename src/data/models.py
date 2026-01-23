"""
数据库模型定义
"""
from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class Trader(Base):
    """交易者表"""
    __tablename__ = 'traders'

    address = Column(String(42), primary_key=True)  # 钱包地址
    win_rate = Column(Float, nullable=False)  # 胜率
    total_markets = Column(Integer, default=0)  # 总交易市场数
    winning_markets = Column(Integer, default=0)  # 盈利市场数
    losing_markets = Column(Integer, default=0)  # 亏损市场数
    overall_pnl = Column(Float, default=0.0)  # 总盈亏
    total_wins = Column(Float, default=0.0)  # 总盈利
    total_losses = Column(Float, default=0.0)  # 总亏损
    profit_factor = Column(Float, default=0.0)  # 盈利因子
    is_qualified = Column(Boolean, default=False)  # 是否合格
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_win_rate', 'win_rate'),
        Index('idx_qualified', 'is_qualified'),
    )


class Trade(Base):
    """交易记录表（时序数据）"""
    __tablename__ = 'trades'

    id = Column(Integer, primary_key=True, autoincrement=True)
    trader_address = Column(String(42), nullable=False, index=True)
    market_id = Column(String(100), nullable=False)
    side = Column(String(10), nullable=False)  # BUY/SELL
    size = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_trader_time', 'trader_address', 'timestamp'),
    )


class Position(Base):
    """持仓表"""
    __tablename__ = 'positions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    trader_address = Column(String(42), nullable=False, index=True)
    market_id = Column(String(100), nullable=False)
    asset_id = Column(String(100))
    size = Column(Float, default=0.0)
    value = Column(Float, default=0.0)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_trader_market', 'trader_address', 'market_id'),
    )


class CopyTrade(Base):
    """跟单记录表"""
    __tablename__ = 'copy_trades'

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_trader = Column(String(42), nullable=False, index=True)  # 被跟单的交易者
    market_id = Column(String(100), nullable=False)
    side = Column(String(10), nullable=False)
    size = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    kelly_position = Column(Float)  # Kelly 建议仓位
    status = Column(String(20), default='pending')  # pending/executed/failed
    executed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_source_time', 'source_trader', 'created_at'),
    )
