"""
跟单策略引擎
支持多交易者跟踪、动态仓位调整、风险控制
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from loguru import logger
from enum import Enum

try:
    from ..utils.risk_manager import RiskManager, RiskLimits, Position
except ImportError:
    from utils.risk_manager import RiskManager, RiskLimits, Position


class TraderTier(Enum):
    """交易者等级"""
    ELITE = "elite"
    PREMIUM = "premium"
    STANDARD = "standard"


@dataclass
class TrackedTrader:
    """跟踪的交易者"""
    address: str
    tier: TraderTier
    win_rate: float
    sharpe_ratio: float
    avg_win: float
    avg_loss: float
    weight: float = 1.0
    last_update: datetime = field(default_factory=datetime.now)
    current_positions: Set[str] = field(default_factory=set)
    
    @property
    def kelly_optimal(self) -> float:
        if self.avg_loss <= 0:
            return 0.1
        odds = self.avg_win / self.avg_loss
        return max(0, (self.win_rate * odds - (1 - self.win_rate)) / odds)


@dataclass
class CopySignal:
    """跟单信号"""
    trader_address: str
    market_id: str
    side: str
    suggested_size: float
    confidence: float
    timestamp: datetime
    reason: str = ""


class PositionSizer:
    """仓位计算器"""
    
    def __init__(
        self,
        base_kelly_fraction: float = 0.25,
        max_position_pct: float = 0.10,
        volatility_lookback: int = 20,
    ):
        self.base_kelly_fraction = base_kelly_fraction
        self.max_position_pct = max_position_pct
        self.volatility_lookback = volatility_lookback
        self.volatility_cache: Dict[str, float] = {}
        self.correlation_matrix: Optional[pd.DataFrame] = None

    def calculate_kelly(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        kelly_fraction: Optional[float] = None,
    ) -> float:
        if avg_loss <= 0:
            return 0.0
        
        fraction = kelly_fraction or self.base_kelly_fraction
        odds = avg_win / avg_loss
        
        kelly = (win_rate * odds - (1 - win_rate)) / odds
        kelly = kelly * fraction
        
        return max(0, min(kelly, self.max_position_pct))

    def calculate_volatility_adjusted_size(
        self,
        base_size: float,
        market_id: str,
        target_volatility: float = 0.15,
    ) -> float:
        market_vol = self.volatility_cache.get(market_id, 0.20)
        
        if market_vol <= 0:
            return base_size
        
        vol_scalar = target_volatility / market_vol
        vol_scalar = max(0.5, min(vol_scalar, 2.0))
        
        return base_size * vol_scalar

    def calculate_correlation_adjusted_size(
        self,
        base_size: float,
        market_id: str,
        existing_positions: Dict[str, float],
    ) -> float:
        if self.correlation_matrix is None or not existing_positions:
            return base_size
        
        if market_id not in self.correlation_matrix.index:
            return base_size
        
        correlation_penalty = 0.0
        total_exposure = sum(existing_positions.values())
        
        for pos_market, pos_size in existing_positions.items():
            if pos_market in self.correlation_matrix.columns:
                corr = abs(self.correlation_matrix.loc[market_id, pos_market])
                weight = pos_size / total_exposure if total_exposure > 0 else 0
                correlation_penalty += corr * weight
        
        adjustment = 1 - (correlation_penalty * 0.5)
        adjustment = max(0.3, adjustment)
        
        return base_size * adjustment

    def calculate_optimal_position(
        self,
        capital: float,
        trader: TrackedTrader,
        market_id: str,
        market_price: float,
        existing_positions: Dict[str, float],
    ) -> float:
        base_kelly = self.calculate_kelly(
            trader.win_rate,
            trader.avg_win,
            trader.avg_loss,
        )
        
        tier_multipliers = {
            TraderTier.ELITE: 1.2,
            TraderTier.PREMIUM: 1.0,
            TraderTier.STANDARD: 0.8,
        }
        tier_mult = tier_multipliers.get(trader.tier, 1.0)
        
        sharpe_mult = min(1.5, max(0.5, trader.sharpe_ratio / 2.0))
        
        position_pct = base_kelly * tier_mult * sharpe_mult * trader.weight
        
        position_pct = self.calculate_volatility_adjusted_size(
            position_pct, market_id
        )
        
        position_pct = self.calculate_correlation_adjusted_size(
            position_pct, market_id, existing_positions
        )
        
        position_pct = min(position_pct, self.max_position_pct)
        
        position_value = capital * position_pct
        position_size = position_value / market_price if market_price > 0 else 0
        
        return position_size

    def update_volatility(self, market_id: str, prices: List[float]):
        if len(prices) < 2:
            return
        
        returns = pd.Series(prices).pct_change().dropna()
        if len(returns) > 0:
            self.volatility_cache[market_id] = float(returns.std() * np.sqrt(252))

    def update_correlation_matrix(self, returns_df: pd.DataFrame):
        self.correlation_matrix = returns_df.corr()


class CopyTradingStrategy:
    """跟单策略引擎"""

    def __init__(
        self,
        capital: float = 10000,
        max_position_size: float = 0.10,
        kelly_fraction: float = 0.25,
        max_daily_loss: float = 0.05,
        max_drawdown: float = 0.20,
        max_traders: int = 10,
        min_confidence: float = 0.6,
    ):
        self.capital = capital
        self.max_position_size = max_position_size
        self.kelly_fraction = kelly_fraction
        self.max_daily_loss = max_daily_loss
        self.max_drawdown = max_drawdown
        self.max_traders = max_traders
        self.min_confidence = min_confidence
        
        self.position_sizer = PositionSizer(
            base_kelly_fraction=kelly_fraction,
            max_position_pct=max_position_size,
        )
        
        self.risk_manager = RiskManager(
            capital,
            RiskLimits(
                max_position_size=max_position_size,
                max_daily_loss=max_daily_loss,
                max_drawdown=max_drawdown,
            )
        )
        
        self.tracked_traders: Dict[str, TrackedTrader] = {}
        self.active_positions: Dict[str, Dict] = {}
        self.pending_signals: List[CopySignal] = []
        self.daily_pnl = 0.0
        self.peak_equity = capital
        self.current_equity = capital

    def add_trader(
        self,
        address: str,
        analysis: Dict,
        tier: TraderTier = TraderTier.STANDARD,
        weight: float = 1.0,
    ):
        if len(self.tracked_traders) >= self.max_traders:
            self._remove_worst_trader()
        
        self.tracked_traders[address] = TrackedTrader(
            address=address,
            tier=tier,
            win_rate=analysis.get('win_rate', 0),
            sharpe_ratio=analysis.get('sharpe_ratio', 0),
            avg_win=analysis.get('avg_win', 0),
            avg_loss=analysis.get('avg_loss', 0),
            weight=weight,
        )
        
        logger.info(f"添加跟踪交易者: {address} ({tier.value})")

    def remove_trader(self, address: str):
        if address in self.tracked_traders:
            del self.tracked_traders[address]
            logger.info(f"移除跟踪交易者: {address}")

    def _remove_worst_trader(self):
        if not self.tracked_traders:
            return
        
        worst = min(
            self.tracked_traders.items(),
            key=lambda x: x[1].win_rate * x[1].sharpe_ratio
        )
        self.remove_trader(worst[0])

    def update_trader_positions(self, address: str, positions: List[Dict]):
        if address not in self.tracked_traders:
            return
        
        trader = self.tracked_traders[address]
        new_positions = {
            pos.get('market', pos.get('asset_id'))
            for pos in positions
        }
        
        new_markets = new_positions - trader.current_positions
        closed_markets = trader.current_positions - new_positions
        
        for market_id in new_markets:
            if self._should_follow_trade(address, market_id):
                self._generate_copy_signal(address, market_id, "BUY")
        
        for market_id in closed_markets:
            if market_id in self.active_positions:
                self._generate_close_signal(address, market_id)
        
        trader.current_positions = new_positions
        trader.last_update = datetime.now()

    def _should_follow_trade(self, trader_address: str, market_id: str) -> bool:
        if self.daily_pnl / self.capital < -self.max_daily_loss:
            logger.warning("日亏损限制触发，停止跟单")
            return False
        
        drawdown = (self.peak_equity - self.current_equity) / self.peak_equity
        if drawdown > self.max_drawdown:
            logger.warning("最大回撤限制触发，停止跟单")
            return False
        
        if market_id in self.active_positions:
            return False
        
        return True

    def _generate_copy_signal(self, trader_address: str, market_id: str, side: str):
        trader = self.tracked_traders.get(trader_address)
        if not trader:
            return
        
        confidence = self._calculate_signal_confidence(trader, market_id)
        
        if confidence < self.min_confidence:
            logger.debug(f"信号置信度不足: {confidence:.2f}")
            return
        
        existing_exposures = {
            pos['market_id']: pos['size'] * pos['price']
            for pos in self.active_positions.values()
        }
        
        suggested_size = self.position_sizer.calculate_optimal_position(
            capital=self.current_equity,
            trader=trader,
            market_id=market_id,
            market_price=1.0,
            existing_positions=existing_exposures,
        )
        
        signal = CopySignal(
            trader_address=trader_address,
            market_id=market_id,
            side=side,
            suggested_size=suggested_size,
            confidence=confidence,
            timestamp=datetime.now(),
            reason=f"跟随 {trader_address[:8]}... 的新仓位",
        )
        
        self.pending_signals.append(signal)
        logger.info(f"生成跟单信号: {market_id} {side} (置信度: {confidence:.2f})")

    def _generate_close_signal(self, trader_address: str, market_id: str):
        if market_id not in self.active_positions:
            return
        
        position = self.active_positions[market_id]
        
        signal = CopySignal(
            trader_address=trader_address,
            market_id=market_id,
            side="SELL",
            suggested_size=position['size'],
            confidence=1.0,
            timestamp=datetime.now(),
            reason=f"跟随 {trader_address[:8]}... 平仓",
        )
        
        self.pending_signals.append(signal)

    def _calculate_signal_confidence(self, trader: TrackedTrader, market_id: str) -> float:
        confidence = 0.0
        
        confidence += min(trader.win_rate, 1.0) * 0.4
        
        sharpe_score = min(trader.sharpe_ratio / 3.0, 1.0)
        confidence += sharpe_score * 0.3
        
        tier_scores = {
            TraderTier.ELITE: 1.0,
            TraderTier.PREMIUM: 0.7,
            TraderTier.STANDARD: 0.4,
        }
        confidence += tier_scores.get(trader.tier, 0.4) * 0.2
        
        recency = (datetime.now() - trader.last_update).total_seconds() / 3600
        recency_score = max(0, 1 - recency / 24)
        confidence += recency_score * 0.1
        
        return min(confidence, 1.0)

    def get_pending_signals(self) -> List[CopySignal]:
        signals = self.pending_signals.copy()
        self.pending_signals.clear()
        return signals

    def execute_signal(
        self,
        signal: CopySignal,
        execution_price: float,
        actual_size: Optional[float] = None,
    ) -> Dict:
        size = actual_size or signal.suggested_size
        
        approved, reason, suggested = self.risk_manager.check_new_trade(
            market_id=signal.market_id,
            side=signal.side,
            size=size,
            price=execution_price,
        )
        
        if not approved:
            logger.warning(f"交易被风控拒绝: {reason}")
            if suggested > 0:
                size = suggested
            else:
                return {"status": "rejected", "reason": reason}
        
        if signal.side == "BUY":
            self.active_positions[signal.market_id] = {
                "market_id": signal.market_id,
                "size": size,
                "price": execution_price,
                "trader": signal.trader_address,
                "timestamp": signal.timestamp,
            }
            
            self.risk_manager.add_position(Position(
                market_id=signal.market_id,
                side="BUY",
                size=size,
                entry_price=execution_price,
                current_price=execution_price,
                timestamp=signal.timestamp,
            ))
            
            logger.info(f"执行买入: {signal.market_id} {size} @ {execution_price}")
            
        else:
            if signal.market_id in self.active_positions:
                pos = self.active_positions[signal.market_id]
                pnl = (execution_price - pos['price']) * pos['size']
                
                self.daily_pnl += pnl
                self.current_equity += pnl
                self.peak_equity = max(self.peak_equity, self.current_equity)
                
                self.risk_manager.remove_position(signal.market_id, execution_price)
                del self.active_positions[signal.market_id]
                
                logger.info(f"执行卖出: {signal.market_id} PnL: ${pnl:.2f}")
                
                return {"status": "executed", "pnl": pnl}
        
        return {"status": "executed", "size": size, "price": execution_price}

    def update_position_prices(self, prices: Dict[str, float]):
        for market_id, price in prices.items():
            if market_id in self.active_positions:
                self.active_positions[market_id]['current_price'] = price
        
        self.risk_manager.update_prices(prices)
        
        unrealized_pnl = sum(
            (pos.get('current_price', pos['price']) - pos['price']) * pos['size']
            for pos in self.active_positions.values()
        )
        self.current_equity = self.capital + self.daily_pnl + unrealized_pnl

    def get_portfolio_summary(self) -> Dict:
        total_exposure = sum(
            pos['size'] * pos.get('current_price', pos['price'])
            for pos in self.active_positions.values()
        )
        
        unrealized_pnl = sum(
            (pos.get('current_price', pos['price']) - pos['price']) * pos['size']
            for pos in self.active_positions.values()
        )
        
        drawdown = (self.peak_equity - self.current_equity) / self.peak_equity
        
        return {
            "tracked_traders": len(self.tracked_traders),
            "active_positions": len(self.active_positions),
            "total_exposure": total_exposure,
            "exposure_pct": total_exposure / self.current_equity if self.current_equity > 0 else 0,
            "unrealized_pnl": unrealized_pnl,
            "daily_pnl": self.daily_pnl,
            "current_equity": self.current_equity,
            "peak_equity": self.peak_equity,
            "drawdown": drawdown,
            "pending_signals": len(self.pending_signals),
        }

    def reset_daily(self):
        self.daily_pnl = 0.0
        self.risk_manager.reset_daily()
        logger.info("日内数据已重置")

    def rank_traders(self) -> List[Tuple[str, float]]:
        rankings = []
        for addr, trader in self.tracked_traders.items():
            score = (
                trader.win_rate * 0.4 +
                min(trader.sharpe_ratio / 3, 1) * 0.3 +
                trader.weight * 0.2 +
                (1 if trader.tier == TraderTier.ELITE else 0.5) * 0.1
            )
            rankings.append((addr, score))
        
        return sorted(rankings, key=lambda x: x[1], reverse=True)
