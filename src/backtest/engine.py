"""
回测引擎
支持事件驱动回测和策略验证
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from loguru import logger
from enum import Enum
from abc import ABC, abstractmethod

try:
    from .results import BacktestResults
    from ..utils.risk_manager import RiskManager, RiskLimits, Position
except ImportError:
    from backtest.results import BacktestResults
    from utils.risk_manager import RiskManager, RiskLimits, Position


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Order:
    market_id: str
    side: OrderSide
    size: float
    price: float
    order_type: OrderType = OrderType.MARKET
    timestamp: datetime = field(default_factory=datetime.now)
    filled: bool = False
    fill_price: float = 0.0


@dataclass
class MarketData:
    market_id: str
    timestamp: datetime
    price: float
    volume: float
    bid: float = 0.0
    ask: float = 0.0
    
    @property
    def spread(self) -> float:
        if self.bid > 0 and self.ask > 0:
            return (self.ask - self.bid) / self.bid
        return 0.0


class BaseStrategy(ABC):
    """策略基类"""
    
    def __init__(self):
        self.positions: Dict[str, Position] = {}
        self.pending_orders: List[Order] = []
    
    @abstractmethod
    def on_data(self, data: MarketData, context: Dict) -> List[Order]:
        pass
    
    def on_trade(self, order: Order, fill_price: float):
        pass
    
    def on_position_close(self, market_id: str, pnl: float):
        pass


class CopyTradingBacktestStrategy(BaseStrategy):
    """跟单策略回测版本"""
    
    def __init__(
        self,
        target_traders: List[str],
        trader_trades: Dict[str, List[Dict]],
        kelly_fraction: float = 0.5,
        max_position_size: float = 0.1,
    ):
        super().__init__()
        self.target_traders = target_traders
        self.trader_trades = trader_trades
        self.kelly_fraction = kelly_fraction
        self.max_position_size = max_position_size
        
        self.trade_index: Dict[str, int] = {t: 0 for t in target_traders}
        self.followed_positions: set = set()
    
    def on_data(self, data: MarketData, context: Dict) -> List[Order]:
        orders = []
        current_time = data.timestamp
        capital = context.get('equity', 10000)
        
        for trader in self.target_traders:
            trades = self.trader_trades.get(trader, [])
            idx = self.trade_index[trader]
            
            while idx < len(trades):
                trade = trades[idx]
                trade_time = pd.to_datetime(trade.get('timestamp', 0), unit='s')
                
                if trade_time > current_time:
                    break
                
                market_id = trade.get('market', trade.get('asset_id'))
                side = trade.get('side')
                
                if market_id == data.market_id:
                    position_key = f"{trader}_{market_id}"
                    
                    if position_key not in self.followed_positions:
                        position_size = min(
                            capital * self.max_position_size * self.kelly_fraction,
                            capital * 0.05
                        ) / data.price
                        
                        orders.append(Order(
                            market_id=market_id,
                            side=OrderSide.BUY if side == "BUY" else OrderSide.SELL,
                            size=position_size,
                            price=data.price,
                            timestamp=current_time,
                        ))
                        
                        self.followed_positions.add(position_key)
                
                idx += 1
            
            self.trade_index[trader] = idx
        
        return orders


class BacktestEngine:
    """回测引擎"""
    
    def __init__(
        self,
        initial_capital: float = 10000,
        commission: float = 0.001,
        slippage: float = 0.001,
        risk_limits: Optional[RiskLimits] = None,
    ):
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.risk_manager = RiskManager(initial_capital, risk_limits)
        
        self.equity = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        
        self.trades: List[Dict] = []
        self.equity_curve: List[float] = [initial_capital]
        self.timestamps: List[datetime] = []
        
        self.strategy: Optional[BaseStrategy] = None

    def set_strategy(self, strategy: BaseStrategy):
        self.strategy = strategy

    def run(
        self,
        data: pd.DataFrame,
        market_id_col: str = "market_id",
        timestamp_col: str = "timestamp",
        price_col: str = "price",
        volume_col: str = "volume",
    ) -> BacktestResults:
        if self.strategy is None:
            raise ValueError("未设置策略")
        
        data = data.sort_values(timestamp_col)
        
        logger.info(f"开始回测: {len(data)} 条数据")
        
        for idx, row in data.iterrows():
            market_data = MarketData(
                market_id=row[market_id_col],
                timestamp=pd.to_datetime(row[timestamp_col]),
                price=float(row[price_col]),
                volume=float(row.get(volume_col, 0)),
                bid=float(row.get('bid', row[price_col] * 0.999)),
                ask=float(row.get('ask', row[price_col] * 1.001)),
            )
            
            self._update_positions(market_data)
            
            context = {
                'equity': self.equity,
                'cash': self.cash,
                'positions': self.positions,
                'timestamp': market_data.timestamp,
            }
            
            orders = self.strategy.on_data(market_data, context)
            
            for order in orders:
                self._process_order(order, market_data)
            
            self._check_risk_limits(market_data)
            
            self.equity_curve.append(self.equity)
            self.timestamps.append(market_data.timestamp)
        
        self._close_all_positions()
        
        logger.info(f"回测完成: 最终权益 ${self.equity:.2f}")
        
        return BacktestResults(
            initial_capital=self.initial_capital,
            final_capital=self.equity,
            trades=self.trades,
            equity_curve=self.equity_curve,
            timestamps=self.timestamps,
        )

    def run_from_trades(
        self,
        trades_data: List[Dict],
        market_prices: Dict[str, List[Dict]],
    ) -> BacktestResults:
        all_events = []
        
        for trade in trades_data:
            all_events.append({
                'type': 'trade',
                'timestamp': pd.to_datetime(trade.get('timestamp', 0), unit='s'),
                'data': trade,
            })
        
        for market_id, prices in market_prices.items():
            for p in prices:
                all_events.append({
                    'type': 'price',
                    'timestamp': pd.to_datetime(p.get('timestamp', 0), unit='s'),
                    'market_id': market_id,
                    'price': float(p.get('price', 0)),
                    'volume': float(p.get('volume', 0)),
                })
        
        all_events.sort(key=lambda x: x['timestamp'])
        
        for event in all_events:
            if event['type'] == 'price':
                market_data = MarketData(
                    market_id=event['market_id'],
                    timestamp=event['timestamp'],
                    price=event['price'],
                    volume=event['volume'],
                )
                self._update_positions(market_data)
            
            elif event['type'] == 'trade':
                trade = event['data']
                market_id = trade.get('market', trade.get('asset_id'))
                
                if market_id in self.positions:
                    continue
                
                order = Order(
                    market_id=market_id,
                    side=OrderSide.BUY if trade.get('side') == 'BUY' else OrderSide.SELL,
                    size=float(trade.get('size', 0)),
                    price=float(trade.get('price', 0)),
                    timestamp=event['timestamp'],
                )
                
                self._execute_order(order)
            
            self.equity_curve.append(self.equity)
            self.timestamps.append(event['timestamp'])
        
        self._close_all_positions()
        
        return BacktestResults(
            initial_capital=self.initial_capital,
            final_capital=self.equity,
            trades=self.trades,
            equity_curve=self.equity_curve,
            timestamps=self.timestamps,
        )

    def _process_order(self, order: Order, market_data: MarketData):
        approved, reason, suggested_size = self.risk_manager.check_new_trade(
            market_id=order.market_id,
            side=order.side.value,
            size=order.size,
            price=order.price,
            market_volume=market_data.volume,
        )
        
        if not approved:
            logger.debug(f"订单被拒绝: {reason}")
            if suggested_size > 0:
                order.size = suggested_size
            else:
                return
        
        self._execute_order(order)

    def _execute_order(self, order: Order):
        if order.side == OrderSide.BUY:
            fill_price = order.price * (1 + self.slippage)
        else:
            fill_price = order.price * (1 - self.slippage)
        
        trade_value = order.size * fill_price
        commission = trade_value * self.commission
        
        if order.side == OrderSide.BUY:
            if self.cash < trade_value + commission:
                order.size = (self.cash - commission) / fill_price
                trade_value = order.size * fill_price
            
            self.cash -= trade_value + commission
            
            self.positions[order.market_id] = Position(
                market_id=order.market_id,
                side=order.side.value,
                size=order.size,
                entry_price=fill_price,
                current_price=fill_price,
                timestamp=order.timestamp,
            )
        
        else:
            if order.market_id in self.positions:
                pos = self.positions[order.market_id]
                pnl = (fill_price - pos.entry_price) * pos.size
                if pos.side == "SELL":
                    pnl = -pnl
                
                self.cash += trade_value - commission + pnl
                
                self.trades.append({
                    'market_id': order.market_id,
                    'side': pos.side,
                    'size': pos.size,
                    'entry_price': pos.entry_price,
                    'exit_price': fill_price,
                    'pnl': pnl - commission,
                    'timestamp': order.timestamp,
                })
                
                del self.positions[order.market_id]
                
                if self.strategy:
                    self.strategy.on_position_close(order.market_id, pnl)
        
        order.filled = True
        order.fill_price = fill_price
        
        if self.strategy:
            self.strategy.on_trade(order, fill_price)
        
        self._update_equity()

    def _update_positions(self, market_data: MarketData):
        if market_data.market_id in self.positions:
            self.positions[market_data.market_id].current_price = market_data.price
        self._update_equity()

    def _update_equity(self):
        position_value = sum(
            p.size * p.current_price for p in self.positions.values()
        )
        self.equity = self.cash + position_value

    def _check_risk_limits(self, market_data: MarketData):
        positions_to_close = []
        
        for market_id, pos in self.positions.items():
            should_stop, reason = self.risk_manager.check_stop_loss(pos)
            if should_stop:
                logger.info(f"{reason}: {market_id}")
                positions_to_close.append((market_id, pos.current_price))
        
        for market_id, price in positions_to_close:
            close_order = Order(
                market_id=market_id,
                side=OrderSide.SELL,
                size=self.positions[market_id].size,
                price=price,
            )
            self._execute_order(close_order)

    def _close_all_positions(self):
        for market_id in list(self.positions.keys()):
            pos = self.positions[market_id]
            close_order = Order(
                market_id=market_id,
                side=OrderSide.SELL,
                size=pos.size,
                price=pos.current_price,
            )
            self._execute_order(close_order)

    def reset(self):
        self.equity = self.initial_capital
        self.cash = self.initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = [self.initial_capital]
        self.timestamps = []
        self.risk_manager = RiskManager(self.initial_capital, self.risk_manager.limits)
