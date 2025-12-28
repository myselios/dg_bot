"""
백테스트 실행 및 결과 관리
"""
from typing import List
import pandas as pd
import numpy as np
from .backtester import Backtester, BacktestResult
from .strategy import Strategy
from .performance import PerformanceAnalyzer


class BacktestRunner:
    """백테스트 실행 및 결과 관리"""
    
    @staticmethod
    def run_backtest(
        strategy: Strategy,
        data: pd.DataFrame,
        ticker: str,
        initial_capital: float = 10_000_000,
        commission: float = 0.0005,
        slippage: float = 0.0001
    ) -> BacktestResult:
        """백테스트 실행"""
        
        backtester = Backtester(
            strategy=strategy,
            data=data,
            ticker=ticker,
            initial_capital=initial_capital,
            commission=commission,
            slippage=slippage
        )
        
        result = backtester.run()
        
        return result
    
    @staticmethod
    def plot_results(result: BacktestResult):
        """결과 시각화"""
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("matplotlib가 설치되지 않아 시각화를 건너뜁니다.")
            return
        
        fig, axes = plt.subplots(3, 2, figsize=(15, 12))
        
        # 1. 자산 곡선
        axes[0, 0].plot(result.equity_curve)
        axes[0, 0].set_title('Equity Curve')
        axes[0, 0].set_ylabel('KRW')
        axes[0, 0].grid(True)
        
        # 2. 낙폭 곡선
        drawdown = BacktestRunner._calculate_drawdown_series(result.equity_curve)
        axes[0, 1].fill_between(range(len(drawdown)), drawdown, 0, alpha=0.3, color='red')
        axes[0, 1].set_title('Drawdown')
        axes[0, 1].set_ylabel('%')
        axes[0, 1].grid(True)
        
        # 3. 거래별 수익
        if result.trades:
            trade_returns = [t.pnl_percent for t in result.trades]
            axes[1, 0].bar(range(len(trade_returns)), trade_returns, 
                           color=['g' if r > 0 else 'r' for r in trade_returns])
            axes[1, 0].set_title('Trade Returns')
            axes[1, 0].set_ylabel('%')
            axes[1, 0].grid(True)
            
            # 4. 누적 수익 분포
            cumulative_returns = np.cumsum(trade_returns)
            axes[1, 1].plot(cumulative_returns)
            axes[1, 1].set_title('Cumulative Returns')
            axes[1, 1].set_ylabel('%')
            axes[1, 1].grid(True)
            
            # 5. 월별 수익률
            monthly_returns = BacktestRunner._calculate_monthly_returns(result.trades)
            if monthly_returns:
                axes[2, 0].bar(range(len(monthly_returns)), list(monthly_returns.values()))
                axes[2, 0].set_title('Monthly Returns')
                axes[2, 0].set_ylabel('%')
                axes[2, 0].set_xticks(range(len(monthly_returns)))
                axes[2, 0].set_xticklabels(list(monthly_returns.keys()), rotation=45)
                axes[2, 0].grid(True)
            
            # 6. 승률 분석
            win_loss = [len([t for t in result.trades if t.pnl > 0]),
                        len([t for t in result.trades if t.pnl < 0])]
            if sum(win_loss) > 0:
                axes[2, 1].pie(win_loss, labels=['Win', 'Loss'], autopct='%1.1f%%')
                axes[2, 1].set_title('Win/Loss Ratio')
        
        plt.tight_layout()
        plt.show()
    
    @staticmethod
    def _calculate_drawdown_series(equity_curve: List[float]) -> List[float]:
        """낙폭 시리즈 계산"""
        if not equity_curve:
            return []
        
        equity_series = pd.Series(equity_curve)
        cumulative_returns = equity_series / equity_series.iloc[0]
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / running_max * 100
        return drawdown.tolist()
    
    @staticmethod
    def _calculate_monthly_returns(trades: List) -> dict:
        """월별 수익률 계산"""
        if not trades:
            return {}
        
        monthly_pnl = {}
        for trade in trades:
            month_key = trade.exit_time.strftime('%Y-%m')
            if month_key not in monthly_pnl:
                monthly_pnl[month_key] = 0
            monthly_pnl[month_key] += trade.pnl_percent
        
        return monthly_pnl
    
    @staticmethod
    def generate_report(result: BacktestResult) -> str:
        """상세 리포트 생성"""
        metrics = result.metrics
        
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║              BACKTEST PERFORMANCE REPORT                      ║
╚══════════════════════════════════════════════════════════════╝

📊 OVERALL PERFORMANCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Initial Capital:        {result.initial_capital:>15,.0f} KRW
Final Equity:          {metrics.get('final_equity', 0):>15,.0f} KRW
Total Return:          {metrics.get('total_return', 0):>15.2f} %
Total Trades:          {metrics.get('total_trades', 0):>15}

🎯 RISK METRICS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Volatility:            {metrics.get('volatility', 0):>15.2f} %
Max Drawdown:          {metrics.get('max_drawdown', 0):>15.2f} %
Sharpe Ratio:          {metrics.get('sharpe_ratio', 0):>15.2f}
Sortino Ratio:         {metrics.get('sortino_ratio', 0):>15.2f}
Calmar Ratio:          {metrics.get('calmar_ratio', 0):>15.2f}

📈 TRADE STATISTICS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Win Rate:              {metrics.get('win_rate', 0):>15.2f} %
Winning Trades:        {metrics.get('winning_trades', 0):>15}
Losing Trades:         {metrics.get('losing_trades', 0):>15}
Average Win:           {metrics.get('avg_win', 0):>15,.0f} KRW
Average Loss:          {metrics.get('avg_loss', 0):>15,.0f} KRW
Profit Factor:         {metrics.get('profit_factor', 0):>15.2f}
Max Consecutive Wins:  {metrics.get('max_consecutive_wins', 0):>15}
Max Consecutive Loss:  {metrics.get('max_consecutive_losses', 0):>15}

⏱️  HOLDING PERIOD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Avg Holding Period:    {metrics.get('avg_holding_period_hours', 0):>15.1f} hours

💰 COSTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Commission:      {metrics.get('total_commission', 0):>15,.0f} KRW
"""
        return report

