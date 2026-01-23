"""
风险管理系统
提供仓位控制、止损、相关性管理等功能
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from loguru import logger
from enum import Enum


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Position:
    market_id: str
    side: str
    size: float
    entry_price: float
    current_price: float
    timestamp: datetime
    category: str = ""
    
    @property
    def pnl(self) -> float:
        if self.side == "BUY":
            return (self.current_price - self.entry_price) * self.size
        return (self.entry_price - self.current_price) * self.size
    
    @property
    def pnl_pct(self) -> float:
        if self.entry_price == 0:
            return 0
        return self.pnl / (self.entry_price * self.size)


@dataclass
class RiskMetrics:
    total_exposure: float = 0.0
    net_exposure: float = 0.0
    var_95: float = 0.0
    var_99: float = 0.0
    expected_shortfall: float = 0.0
    correlation_risk: float = 0.0
    concentration_risk: float = 0.0
    liquidity_risk: float = 0.0
    overall_risk_level: RiskLevel = RiskLevel.LOW
    risk_score: float = 0.0


@dataclass
class RiskLimits:
    max_position_size: float = 0.10
    max_total_exposure: float = 0.80
    max_single_market_exposure: float = 0.15
    max_category_exposure: float = 0.30
    max_correlation: float = 0.70
    max_daily_loss: float = 0.05
    max_drawdown: float = 0.20
    trailing_stop_pct: float = 0.10
    hard_stop_pct: float = 0.15
    take_profit_pct: float = 0.50
    min_liquidity_ratio: float = 0.01


class RiskManager:
    """风险管理器"""

    def __init__(
        self,
        total_capital: float,
        limits: Optional[RiskLimits] = None,
    ):
        self.total_capital = total_capital
        self.limits = limits or RiskLimits()
        self.positions: Dict[str, Position] = {}
        self.daily_pnl = 0.0
        self.peak_equity = total_capital
        self.current_equity = total_capital
        self.trade_history: List[Dict] = []
        self.correlation_matrix: Optional[pd.DataFrame] = None
        self.volatility_cache: Dict[str, float] = {}

    def check_new_trade(
        self,
        market_id: str,
        side: str,
        size: float,
        price: float,
        market_volume: float = 0,
        category: str = "",
    ) -> Tuple[bool, str, float]:
        trade_value = size * price
        
        if trade_value / self.total_capital > self.limits.max_position_size:
            suggested = self.limits.max_position_size * self.total_capital / price
            return False, f"超过单笔仓位限制 ({self.limits.max_position_size:.0%})", suggested
        
        current_exposure = self._calculate_total_exposure()
        if (current_exposure + trade_value) / self.total_capital > self.limits.max_total_exposure:
            available = (self.limits.max_total_exposure * self.total_capital - current_exposure)
            suggested = max(0, available / price)
            return False, f"超过总敞口限制 ({self.limits.max_total_exposure:.0%})", suggested
        
        if market_id in self.positions:
            existing = self.positions[market_id]
            total_exposure = existing.size * existing.current_price + trade_value
            if total_exposure / self.total_capital > self.limits.max_single_market_exposure:
                return False, f"超过单市场敞口限制 ({self.limits.max_single_market_exposure:.0%})", 0
        
        if category:
            category_exposure = self._calculate_category_exposure(category)
            if (category_exposure + trade_value) / self.total_capital > self.limits.max_category_exposure:
                return False, f"超过类别敞口限制 ({self.limits.max_category_exposure:.0%})", 0
        
        if self.daily_pnl / self.total_capital < -self.limits.max_daily_loss:
            return False, f"触发日亏损熔断 ({self.limits.max_daily_loss:.0%})", 0
        
        current_drawdown = (self.peak_equity - self.current_equity) / self.peak_equity
        if current_drawdown > self.limits.max_drawdown:
            return False, f"触发最大回撤限制 ({self.limits.max_drawdown:.0%})", 0
        
        if market_volume > 0:
            liquidity_impact = trade_value / market_volume
            if liquidity_impact > self.limits.min_liquidity_ratio:
                suggested = market_volume * self.limits.min_liquidity_ratio / price
                return False, f"流动性不足，建议减少仓位", suggested
        
        if self.correlation_matrix is not None and len(self.positions) > 0:
            correlation_risk = self._check_correlation_risk(market_id)
            if correlation_risk > self.limits.max_correlation:
                return False, f"相关性风险过高 ({correlation_risk:.2f})", 0
        
        return True, "通过风险检查", size

    def calculate_optimal_position(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        volatility: float = 0.0,
        correlation: float = 0.0,
    ) -> float:
        if avg_loss <= 0:
            return self.limits.max_position_size
        
        odds = avg_win / avg_loss
        kelly = (win_rate * odds - (1 - win_rate)) / odds
        
        kelly = kelly * 0.5
        
        if volatility > 0:
            vol_adjustment = 1 / (1 + volatility)
            kelly *= vol_adjustment
        
        if correlation > 0:
            correlation_adjustment = 1 - (correlation * 0.5)
            kelly *= correlation_adjustment
        
        kelly = max(0, min(kelly, self.limits.max_position_size))
        
        return kelly

    def check_stop_loss(self, position: Position) -> Tuple[bool, str]:
        pnl_pct = position.pnl_pct
        
        if pnl_pct <= -self.limits.hard_stop_pct:
            return True, f"触发硬止损 ({self.limits.hard_stop_pct:.0%})"
        
        return False, ""

    def check_trailing_stop(
        self,
        position: Position,
        peak_price: float,
    ) -> Tuple[bool, str]:
        if position.side == "BUY":
            drawdown_from_peak = (peak_price - position.current_price) / peak_price
        else:
            drawdown_from_peak = (position.current_price - peak_price) / peak_price
        
        if drawdown_from_peak >= self.limits.trailing_stop_pct:
            return True, f"触发追踪止损 ({self.limits.trailing_stop_pct:.0%})"
        
        return False, ""

    def check_take_profit(self, position: Position) -> Tuple[bool, str]:
        if position.pnl_pct >= self.limits.take_profit_pct:
            return True, f"触发止盈 ({self.limits.take_profit_pct:.0%})"
        return False, ""

    def add_position(self, position: Position):
        self.positions[position.market_id] = position
        logger.info(f"添加仓位: {position.market_id} {position.side} {position.size} @ {position.entry_price}")

    def remove_position(self, market_id: str, exit_price: float):
        if market_id not in self.positions:
            return
        
        position = self.positions[market_id]
        position.current_price = exit_price
        realized_pnl = position.pnl
        
        self.daily_pnl += realized_pnl
        self.current_equity += realized_pnl
        self.peak_equity = max(self.peak_equity, self.current_equity)
        
        self.trade_history.append({
            "market_id": market_id,
            "side": position.side,
            "size": position.size,
            "entry_price": position.entry_price,
            "exit_price": exit_price,
            "pnl": realized_pnl,
            "timestamp": datetime.now(),
        })
        
        del self.positions[market_id]
        logger.info(f"平仓: {market_id} PnL: ${realized_pnl:.2f}")

    def update_prices(self, prices: Dict[str, float]):
        for market_id, price in prices.items():
            if market_id in self.positions:
                self.positions[market_id].current_price = price

    def calculate_risk_metrics(self) -> RiskMetrics:
        metrics = RiskMetrics()
        
        if not self.positions:
            return metrics
        
        metrics.total_exposure = self._calculate_total_exposure()
        metrics.net_exposure = self._calculate_net_exposure()
        metrics.concentration_risk = self._calculate_concentration_risk()
        
        if self.correlation_matrix is not None:
            metrics.correlation_risk = self._calculate_portfolio_correlation()
        
        pnl_values = [p.pnl for p in self.positions.values()]
        if pnl_values:
            metrics.var_95 = self._calculate_var(pnl_values, 0.95)
            metrics.var_99 = self._calculate_var(pnl_values, 0.99)
            metrics.expected_shortfall = self._calculate_expected_shortfall(pnl_values, 0.95)
        
        metrics.risk_score = self._calculate_risk_score(metrics)
        metrics.overall_risk_level = self._determine_risk_level(metrics.risk_score)
        
        return metrics

    def update_correlation_matrix(self, returns_df: pd.DataFrame):
        self.correlation_matrix = returns_df.corr()

    def update_volatility(self, market_id: str, volatility: float):
        self.volatility_cache[market_id] = volatility

    def reset_daily(self):
        self.daily_pnl = 0.0
        logger.info("日内数据已重置")

    def _calculate_total_exposure(self) -> float:
        return sum(p.size * p.current_price for p in self.positions.values())

    def _calculate_net_exposure(self) -> float:
        long_exposure = sum(
            p.size * p.current_price 
            for p in self.positions.values() 
            if p.side == "BUY"
        )
        short_exposure = sum(
            p.size * p.current_price 
            for p in self.positions.values() 
            if p.side == "SELL"
        )
        return long_exposure - short_exposure

    def _calculate_category_exposure(self, category: str) -> float:
        return sum(
            p.size * p.current_price
            for p in self.positions.values()
            if p.category == category
        )

    def _calculate_concentration_risk(self) -> float:
        if not self.positions:
            return 0.0
        
        exposures = [p.size * p.current_price for p in self.positions.values()]
        total = sum(exposures)
        if total == 0:
            return 0.0
        
        weights = [e / total for e in exposures]
        hhi = sum(w ** 2 for w in weights)
        
        return hhi

    def _calculate_portfolio_correlation(self) -> float:
        if self.correlation_matrix is None or len(self.positions) < 2:
            return 0.0
        
        market_ids = list(self.positions.keys())
        correlations = []
        
        for i, m1 in enumerate(market_ids):
            for m2 in market_ids[i+1:]:
                if m1 in self.correlation_matrix.index and m2 in self.correlation_matrix.columns:
                    correlations.append(abs(self.correlation_matrix.loc[m1, m2]))
        
        return float(np.mean(correlations)) if correlations else 0.0

    def _check_correlation_risk(self, new_market_id: str) -> float:
        if self.correlation_matrix is None:
            return 0.0
        
        if new_market_id not in self.correlation_matrix.index:
            return 0.0
        
        correlations = []
        for market_id in self.positions.keys():
            if market_id in self.correlation_matrix.columns:
                corr = abs(self.correlation_matrix.loc[new_market_id, market_id])
                correlations.append(corr)
        
        return float(max(correlations)) if correlations else 0.0

    def _calculate_var(self, values: List[float], confidence: float) -> float:
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int((1 - confidence) * len(sorted_values))
        return abs(sorted_values[index]) if index < len(sorted_values) else 0.0

    def _calculate_expected_shortfall(self, values: List[float], confidence: float) -> float:
        if not values:
            return 0.0
        sorted_values = sorted(values)
        cutoff_index = int((1 - confidence) * len(sorted_values))
        tail_values = sorted_values[:cutoff_index + 1]
        return abs(np.mean(tail_values)) if tail_values else 0.0

    def _calculate_risk_score(self, metrics: RiskMetrics) -> float:
        exposure_score = metrics.total_exposure / self.total_capital
        concentration_score = metrics.concentration_risk
        correlation_score = metrics.correlation_risk
        
        drawdown = (self.peak_equity - self.current_equity) / self.peak_equity
        drawdown_score = drawdown / self.limits.max_drawdown
        
        score = (
            exposure_score * 0.3 +
            concentration_score * 0.2 +
            correlation_score * 0.2 +
            drawdown_score * 0.3
        )
        
        return min(1.0, score)

    def _determine_risk_level(self, risk_score: float) -> RiskLevel:
        if risk_score < 0.25:
            return RiskLevel.LOW
        elif risk_score < 0.5:
            return RiskLevel.MEDIUM
        elif risk_score < 0.75:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL

    def get_position_summary(self) -> Dict:
        total_pnl = sum(p.pnl for p in self.positions.values())
        
        return {
            "position_count": len(self.positions),
            "total_exposure": self._calculate_total_exposure(),
            "net_exposure": self._calculate_net_exposure(),
            "unrealized_pnl": total_pnl,
            "daily_pnl": self.daily_pnl,
            "current_equity": self.current_equity,
            "peak_equity": self.peak_equity,
            "drawdown": (self.peak_equity - self.current_equity) / self.peak_equity,
        }
