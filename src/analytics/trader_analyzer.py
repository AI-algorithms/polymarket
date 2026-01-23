"""
交易者分析器
计算胜率、夏普比率、最大回撤等专业量化指标
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from loguru import logger
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class TraderMetrics:
    """交易者指标数据类"""
    total_markets: int = 0
    winning_markets: int = 0
    losing_markets: int = 0
    win_rate: float = 0.0
    total_wins: float = 0.0
    total_losses: float = 0.0
    overall_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    calmar_ratio: float = 0.0
    volatility: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0
    avg_holding_period: float = 0.0
    trade_frequency: float = 0.0
    expectancy: float = 0.0
    risk_adjusted_return: float = 0.0
    consistency_score: float = 0.0
    recent_performance: float = 0.0

    def to_dict(self) -> Dict:
        return self.__dict__.copy()


class TraderAnalyzer:
    """交易者分析器 - 专业量化版"""

    RISK_FREE_RATE = 0.05

    def __init__(
        self,
        min_trades: int = 20,
        min_win_rate: float = 0.90,
        min_sharpe: float = 1.0,
        max_drawdown: float = 0.30,
        lookback_days: int = 90,
    ):
        self.min_trades = min_trades
        self.min_win_rate = min_win_rate
        self.min_sharpe = min_sharpe
        self.max_drawdown = max_drawdown
        self.lookback_days = lookback_days

    def analyze_trader(self, trades: List[Dict], positions: List[Dict]) -> Dict:
        if not trades:
            return TraderMetrics().to_dict()

        df = self._trades_to_dataframe(trades)
        if df.empty:
            return TraderMetrics().to_dict()

        market_pnl = self._calculate_market_pnl(trades, positions)
        pnl_series = self._build_pnl_series(df, positions)
        
        metrics = TraderMetrics()
        
        metrics.total_markets = len(market_pnl)
        metrics.winning_markets = sum(1 for pnl in market_pnl.values() if pnl > 0)
        metrics.losing_markets = sum(1 for pnl in market_pnl.values() if pnl < 0)
        metrics.win_rate = metrics.winning_markets / metrics.total_markets if metrics.total_markets > 0 else 0
        metrics.total_wins = sum(pnl for pnl in market_pnl.values() if pnl > 0)
        metrics.total_losses = abs(sum(pnl for pnl in market_pnl.values() if pnl < 0))
        metrics.overall_pnl = metrics.total_wins - metrics.total_losses
        metrics.avg_win = metrics.total_wins / metrics.winning_markets if metrics.winning_markets > 0 else 0
        metrics.avg_loss = metrics.total_losses / metrics.losing_markets if metrics.losing_markets > 0 else 0
        metrics.profit_factor = metrics.total_wins / metrics.total_losses if metrics.total_losses > 0 else float('inf')

        if len(pnl_series) > 1:
            returns = pnl_series.pct_change().dropna()
            if len(returns) > 0:
                metrics.sharpe_ratio = self._calculate_sharpe_ratio(returns)
                metrics.sortino_ratio = self._calculate_sortino_ratio(returns)
                metrics.volatility = float(returns.std() * np.sqrt(252))
                
                if len(returns) > 2:
                    metrics.skewness = float(returns.skew())
                    metrics.kurtosis = float(returns.kurtosis())

        metrics.max_drawdown, metrics.max_drawdown_duration = self._calculate_max_drawdown(pnl_series)
        
        if metrics.max_drawdown > 0:
            annualized_return = metrics.overall_pnl / max(len(pnl_series), 1) * 252
            metrics.calmar_ratio = annualized_return / metrics.max_drawdown

        metrics.expectancy = self._calculate_expectancy(metrics)
        metrics.avg_holding_period = self._calculate_avg_holding_period(df)
        metrics.trade_frequency = self._calculate_trade_frequency(df)
        metrics.consistency_score = self._calculate_consistency_score(market_pnl)
        metrics.recent_performance = self._calculate_recent_performance(df, self.lookback_days)
        metrics.risk_adjusted_return = self._calculate_risk_adjusted_return(metrics)

        return metrics.to_dict()

    def _trades_to_dataframe(self, trades: List[Dict]) -> pd.DataFrame:
        if not trades:
            return pd.DataFrame()
        
        df = pd.DataFrame(trades)
        
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', errors='coerce')
        elif 'created_at' in df.columns:
            df['timestamp'] = pd.to_datetime(df['created_at'], errors='coerce')
        else:
            df['timestamp'] = pd.Timestamp.now()
        
        for col in ['size', 'price']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        df = df.sort_values('timestamp')
        return df

    def _build_pnl_series(self, df: pd.DataFrame, positions: List[Dict]) -> pd.Series:
        if df.empty:
            return pd.Series([0])
        
        df = df.copy()
        if 'side' not in df.columns:
            df['side'] = 'BUY'
        df['trade_value'] = df.apply(
            lambda x: -x['size'] * x['price'] if x['side'] == 'BUY' else x['size'] * x['price'],
            axis=1
        )
        
        cumulative_pnl = df.groupby('timestamp')['trade_value'].sum().cumsum()
        
        if positions:
            unrealized = sum(float(p.get('value', 0)) for p in positions)
            if len(cumulative_pnl) > 0:
                cumulative_pnl.iloc[-1] += unrealized
        
        return cumulative_pnl

    def _calculate_market_pnl(self, trades: List[Dict], positions: List[Dict]) -> Dict[str, float]:
        market_pnl = defaultdict(float)

        for trade in trades:
            market_id = trade.get("market", trade.get("asset_id"))
            side = trade.get("side")
            size = float(trade.get("size", 0))
            price = float(trade.get("price", 0))

            if side == "BUY":
                market_pnl[market_id] -= size * price
            elif side == "SELL":
                market_pnl[market_id] += size * price

        for position in positions:
            market_id = position.get("market", position.get("asset_id"))
            current_value = float(position.get("value", 0))
            market_pnl[market_id] += current_value

        return dict(market_pnl)

    def _calculate_sharpe_ratio(self, returns: pd.Series) -> float:
        if len(returns) < 2 or returns.std() == 0:
            return 0.0
        
        excess_returns = returns - self.RISK_FREE_RATE / 252
        return float(excess_returns.mean() / returns.std() * np.sqrt(252))

    def _calculate_sortino_ratio(self, returns: pd.Series) -> float:
        if len(returns) < 2:
            return 0.0
        
        excess_returns = returns - self.RISK_FREE_RATE / 252
        downside_returns = returns[returns < 0]
        
        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return float('inf') if excess_returns.mean() > 0 else 0.0
        
        downside_std = downside_returns.std()
        return float(excess_returns.mean() / downside_std * np.sqrt(252))

    def _calculate_max_drawdown(self, pnl_series: pd.Series) -> Tuple[float, int]:
        if len(pnl_series) < 2:
            return 0.0, 0
        
        cummax = pnl_series.cummax()
        drawdown = (cummax - pnl_series) / cummax.replace(0, np.nan)
        drawdown = drawdown.fillna(0)
        
        max_dd = float(drawdown.max()) if len(drawdown) > 0 else 0.0
        
        max_duration = 0
        current_duration = 0
        for dd in drawdown:
            if dd > 0:
                current_duration += 1
                max_duration = max(max_duration, current_duration)
            else:
                current_duration = 0
        
        return max_dd, max_duration

    def _calculate_expectancy(self, metrics: TraderMetrics) -> float:
        win_rate = metrics.win_rate
        avg_win = metrics.avg_win
        avg_loss = metrics.avg_loss
        
        if avg_loss == 0:
            return avg_win * win_rate if win_rate > 0 else 0
        
        return (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

    def _calculate_avg_holding_period(self, df: pd.DataFrame) -> float:
        if df.empty or 'timestamp' not in df.columns:
            return 0.0
        
        market_col = 'market' if 'market' in df.columns else 'asset_id'
        if market_col not in df.columns:
            return 0.0
        
        holding_periods = []
        for market_id, group in df.groupby(market_col):
            if len(group) >= 2:
                duration = (group['timestamp'].max() - group['timestamp'].min()).total_seconds() / 3600
                holding_periods.append(duration)
        
        return float(np.mean(holding_periods)) if holding_periods else 0.0

    def _calculate_trade_frequency(self, df: pd.DataFrame) -> float:
        if df.empty or 'timestamp' not in df.columns:
            return 0.0
        
        date_range = (df['timestamp'].max() - df['timestamp'].min()).days
        if date_range <= 0:
            return float(len(df))
        
        return float(len(df) / date_range)

    def _calculate_consistency_score(self, market_pnl: Dict[str, float]) -> float:
        if not market_pnl:
            return 0.0
        
        pnl_values = list(market_pnl.values())
        if len(pnl_values) < 2:
            return 1.0 if pnl_values[0] > 0 else 0.0
        
        positive_count = sum(1 for p in pnl_values if p > 0)
        consistency = positive_count / len(pnl_values)
        
        pnl_std = np.std(pnl_values)
        pnl_mean = np.mean(pnl_values)
        cv = pnl_std / abs(pnl_mean) if pnl_mean != 0 else float('inf')
        
        stability = 1 / (1 + cv)
        
        return float(consistency * 0.6 + stability * 0.4)

    def _calculate_recent_performance(self, df: pd.DataFrame, lookback_days: int) -> float:
        if df.empty or 'timestamp' not in df.columns:
            return 0.0
        
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=lookback_days)
        recent_df = df[df['timestamp'] >= cutoff]
        
        if recent_df.empty:
            return 0.0
        
        if 'side' not in recent_df.columns:
            return 0.0
        recent_pnl = recent_df.apply(
            lambda x: -x['size'] * x['price'] if x['side'] == 'BUY' else x['size'] * x['price'],
            axis=1
        ).sum()
        
        return float(recent_pnl)

    def _calculate_risk_adjusted_return(self, metrics: TraderMetrics) -> float:
        if metrics.max_drawdown == 0:
            return metrics.overall_pnl
        
        return metrics.overall_pnl / (1 + metrics.max_drawdown)

    def is_qualified_trader(self, analysis: Dict) -> bool:
        return (
            analysis["total_markets"] >= self.min_trades
            and analysis["win_rate"] >= self.min_win_rate
            and analysis["overall_pnl"] > 0
            and analysis["max_drawdown"] <= self.max_drawdown
            and analysis["sharpe_ratio"] >= self.min_sharpe
        )

    def rank_traders(self, traders: List[Dict]) -> List[Dict]:
        if not traders:
            return []
        
        for trader in traders:
            trader['composite_score'] = self._calculate_composite_score(trader)
        
        return sorted(traders, key=lambda x: x['composite_score'], reverse=True)

    def _calculate_composite_score(self, analysis: Dict) -> float:
        weights = {
            'sharpe_ratio': 0.25,
            'sortino_ratio': 0.15,
            'win_rate': 0.20,
            'profit_factor': 0.15,
            'consistency_score': 0.15,
            'risk_adjusted_return': 0.10,
        }
        
        score = 0.0
        
        sharpe = min(analysis.get('sharpe_ratio', 0), 5) / 5
        score += weights['sharpe_ratio'] * sharpe
        
        sortino = min(analysis.get('sortino_ratio', 0), 5) / 5
        score += weights['sortino_ratio'] * sortino
        
        score += weights['win_rate'] * analysis.get('win_rate', 0)
        
        pf = min(analysis.get('profit_factor', 0), 10) / 10
        score += weights['profit_factor'] * pf
        
        score += weights['consistency_score'] * analysis.get('consistency_score', 0)
        
        rar = analysis.get('risk_adjusted_return', 0)
        rar_normalized = 1 / (1 + np.exp(-rar / 1000))
        score += weights['risk_adjusted_return'] * rar_normalized
        
        return float(score)

    def _empty_result(self) -> Dict:
        return TraderMetrics().to_dict()
