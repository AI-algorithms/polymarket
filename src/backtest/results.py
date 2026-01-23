"""
回测结果分析
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class BacktestResults:
    """回测结果"""
    initial_capital: float
    final_capital: float
    trades: List[Dict] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    timestamps: List[datetime] = field(default_factory=list)
    
    @property
    def total_return(self) -> float:
        return (self.final_capital - self.initial_capital) / self.initial_capital
    
    @property
    def total_pnl(self) -> float:
        return self.final_capital - self.initial_capital
    
    @property
    def total_trades(self) -> int:
        return len(self.trades)
    
    @property
    def winning_trades(self) -> int:
        return sum(1 for t in self.trades if t.get('pnl', 0) > 0)
    
    @property
    def losing_trades(self) -> int:
        return sum(1 for t in self.trades if t.get('pnl', 0) < 0)
    
    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0
        return self.winning_trades / self.total_trades
    
    @property
    def profit_factor(self) -> float:
        gross_profit = sum(t['pnl'] for t in self.trades if t.get('pnl', 0) > 0)
        gross_loss = abs(sum(t['pnl'] for t in self.trades if t.get('pnl', 0) < 0))
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0
        return gross_profit / gross_loss
    
    @property
    def max_drawdown(self) -> float:
        if not self.equity_curve:
            return 0
        equity = pd.Series(self.equity_curve)
        peak = equity.cummax()
        drawdown = (peak - equity) / peak
        return float(drawdown.max())
    
    @property
    def sharpe_ratio(self) -> float:
        if len(self.equity_curve) < 2:
            return 0
        returns = pd.Series(self.equity_curve).pct_change().dropna()
        if returns.std() == 0:
            return 0
        return float(returns.mean() / returns.std() * np.sqrt(252))
    
    @property
    def sortino_ratio(self) -> float:
        if len(self.equity_curve) < 2:
            return 0
        returns = pd.Series(self.equity_curve).pct_change().dropna()
        downside = returns[returns < 0]
        if len(downside) == 0 or downside.std() == 0:
            return float('inf') if returns.mean() > 0 else 0
        return float(returns.mean() / downside.std() * np.sqrt(252))
    
    @property
    def calmar_ratio(self) -> float:
        if self.max_drawdown == 0:
            return float('inf') if self.total_return > 0 else 0
        annualized_return = self.total_return * (252 / max(len(self.equity_curve), 1))
        return annualized_return / self.max_drawdown
    
    @property
    def avg_trade_pnl(self) -> float:
        if not self.trades:
            return 0
        return sum(t.get('pnl', 0) for t in self.trades) / len(self.trades)
    
    @property
    def avg_win(self) -> float:
        wins = [t['pnl'] for t in self.trades if t.get('pnl', 0) > 0]
        return sum(wins) / len(wins) if wins else 0
    
    @property
    def avg_loss(self) -> float:
        losses = [t['pnl'] for t in self.trades if t.get('pnl', 0) < 0]
        return abs(sum(losses) / len(losses)) if losses else 0
    
    @property
    def expectancy(self) -> float:
        return (self.win_rate * self.avg_win) - ((1 - self.win_rate) * self.avg_loss)
    
    @property
    def max_consecutive_wins(self) -> int:
        return self._max_consecutive(lambda t: t.get('pnl', 0) > 0)
    
    @property
    def max_consecutive_losses(self) -> int:
        return self._max_consecutive(lambda t: t.get('pnl', 0) < 0)
    
    def _max_consecutive(self, condition) -> int:
        max_count = 0
        current = 0
        for t in self.trades:
            if condition(t):
                current += 1
                max_count = max(max_count, current)
            else:
                current = 0
        return max_count
    
    def get_monthly_returns(self) -> pd.Series:
        if not self.equity_curve or not self.timestamps:
            return pd.Series()
        
        df = pd.DataFrame({
            'equity': self.equity_curve,
            'date': self.timestamps
        })
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        
        monthly = df['equity'].resample('M').last()
        return monthly.pct_change().dropna()
    
    def get_daily_returns(self) -> pd.Series:
        if len(self.equity_curve) < 2:
            return pd.Series()
        return pd.Series(self.equity_curve).pct_change().dropna()
    
    def summary(self) -> Dict:
        return {
            "initial_capital": self.initial_capital,
            "final_capital": self.final_capital,
            "total_return": f"{self.total_return:.2%}",
            "total_pnl": f"${self.total_pnl:.2f}",
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": f"{self.win_rate:.2%}",
            "profit_factor": f"{self.profit_factor:.2f}",
            "max_drawdown": f"{self.max_drawdown:.2%}",
            "sharpe_ratio": f"{self.sharpe_ratio:.2f}",
            "sortino_ratio": f"{self.sortino_ratio:.2f}",
            "calmar_ratio": f"{self.calmar_ratio:.2f}",
            "avg_trade_pnl": f"${self.avg_trade_pnl:.2f}",
            "avg_win": f"${self.avg_win:.2f}",
            "avg_loss": f"${self.avg_loss:.2f}",
            "expectancy": f"${self.expectancy:.2f}",
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
        }
    
    def print_summary(self):
        print("\n" + "=" * 50)
        print("           回测结果摘要")
        print("=" * 50)
        
        summary = self.summary()
        for key, value in summary.items():
            label = key.replace('_', ' ').title()
            print(f"{label:.<30} {value}")
        
        print("=" * 50)
