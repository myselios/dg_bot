"""
성과 분석 클래스
"""
from typing import List, Dict, Any
import pandas as pd
import numpy as np
from .portfolio import Trade


class PerformanceAnalyzer:
    """성과 분석"""
    
    @staticmethod
    def calculate_metrics(
        equity_curve: List[float],
        trades: List[Trade],
        initial_capital: float
    ) -> Dict[str, Any]:
        """핵심 성과 지표 계산"""
        
        if not equity_curve:
            return {}
        
        equity_series = pd.Series(equity_curve)
        returns = equity_series.pct_change().dropna()
        
        # 1. 수익 지표
        total_return = (equity_curve[-1] - initial_capital) / initial_capital * 100
        
        # 2. 리스크 지표
        volatility = returns.std() * np.sqrt(365) * 100 if len(returns) > 0 else 0  # 연율화
        max_drawdown = PerformanceAnalyzer._calculate_max_drawdown(equity_series)
        
        # 3. 위험 조정 수익률
        sharpe_ratio = PerformanceAnalyzer._calculate_sharpe(returns) if len(returns) > 0 else 0
        sortino_ratio = PerformanceAnalyzer._calculate_sortino(returns) if len(returns) > 0 else 0
        calmar_ratio = total_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        # 4. 거래 통계
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl < 0]
        
        win_rate = len(winning_trades) / len(trades) * 100 if trades else 0
        
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0
        
        profit_factor = (
            abs(sum(t.pnl for t in winning_trades)) / 
            abs(sum(t.pnl for t in losing_trades))
            if losing_trades and sum(t.pnl for t in losing_trades) != 0 else float('inf')
        )
        
        # 5. 최대 연속 손익
        max_consecutive_wins = PerformanceAnalyzer._max_consecutive(
            [t.pnl > 0 for t in trades]
        )
        max_consecutive_losses = PerformanceAnalyzer._max_consecutive(
            [t.pnl < 0 for t in trades]
        )
        
        # 6. 평균 보유 기간
        avg_holding_period = np.mean([
            t.holding_period.total_seconds() / 3600 
            for t in trades
        ]) if trades else 0
        
        return {
            # 수익 지표
            'total_return': total_return,
            'total_trades': len(trades),
            'final_equity': equity_curve[-1],
            
            # 리스크 지표
            'volatility': volatility,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'calmar_ratio': calmar_ratio,
            
            # 거래 통계
            'win_rate': win_rate,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_consecutive_wins': max_consecutive_wins,
            'max_consecutive_losses': max_consecutive_losses,
            
            # 기타
            'avg_holding_period_hours': avg_holding_period,
            'total_commission': sum(t.commission for t in trades)
        }
    
    @staticmethod
    def _calculate_max_drawdown(equity_series: pd.Series) -> float:
        """최대 낙폭 계산"""
        if len(equity_series) == 0:
            return 0.0
        
        cumulative_returns = equity_series / equity_series.iloc[0]
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / running_max * 100
        return drawdown.min()
    
    @staticmethod
    def _calculate_sharpe(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """샤프 비율"""
        if len(returns) == 0 or returns.std() == 0:
            return 0
        
        excess_returns = returns - (risk_free_rate / 365)
        if excess_returns.std() == 0:
            return 0
        return (excess_returns.mean() / excess_returns.std()) * np.sqrt(365)
    
    @staticmethod
    def _calculate_sortino(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """소르티노 비율 (하방 리스크만 고려)"""
        if len(returns) == 0:
            return 0
        
        excess_returns = returns - (risk_free_rate / 365)
        downside_returns = excess_returns[excess_returns < 0]
        
        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0
        
        return (excess_returns.mean() / downside_returns.std()) * np.sqrt(365)
    
    @staticmethod
    def _max_consecutive(boolean_list: List[bool]) -> int:
        """최대 연속 True 개수"""
        max_count = 0
        current_count = 0
        
        for val in boolean_list:
            if val:
                current_count += 1
                max_count = max(max_count, current_count)
            else:
                current_count = 0
        
        return max_count




