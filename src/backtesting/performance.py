"""
성과 분석 클래스
"""
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from .portfolio import Trade


class PerformanceAnalyzer:
    """성과 분석"""

    # 데이터 간격별 연율화 상수 (1년 기준 봉 개수)
    ANNUALIZATION_FACTORS = {
        'day': 365,                    # 일봉: 365일 (코인 24/7)
        'minute60': 365 * 24,          # 시봉: 8,760시간
        'minute30': 365 * 24 * 2,      # 30분봉: 17,520개
        'minute15': 365 * 24 * 4,      # 15분봉: 35,040개
        'minute5': 365 * 24 * 12,      # 5분봉: 105,120개
        'minute1': 365 * 24 * 60,      # 1분봉: 525,600개
        'week': 52,                    # 주봉: 52주
    }

    @staticmethod
    def _get_annualization_factor(data_interval: str) -> int:
        """
        데이터 간격에 따른 연율화 상수 반환

        Args:
            data_interval: 데이터 간격 ('day', 'minute60', 'minute15', 등)

        Returns:
            연율화 상수 (1년 기준 봉 개수)
        """
        return PerformanceAnalyzer.ANNUALIZATION_FACTORS.get(data_interval, 365)

    @staticmethod
    def calculate_metrics(
        equity_curve: List[float],
        trades: List[Trade],
        initial_capital: float,
        data_interval: str = 'day'  # 데이터 간격 파라미터 추가
    ) -> Dict[str, Any]:
        """
        핵심 성과 지표 계산

        Args:
            equity_curve: 자산 곡선
            trades: 거래 목록
            initial_capital: 초기 자본
            data_interval: 데이터 간격 ('day', 'minute60', 'minute15', 등)
                          연율화 계산에 사용됨

        Returns:
            성과 지표 딕셔너리
        """

        if not equity_curve:
            return {}

        equity_series = pd.Series(equity_curve)
        returns = equity_series.pct_change().dropna()

        # 연율화 상수 (데이터 간격에 따라 동적 결정)
        annualization_factor = PerformanceAnalyzer._get_annualization_factor(data_interval)

        # 1. 수익 지표
        total_return = (equity_curve[-1] - initial_capital) / initial_capital * 100

        # 2. 리스크 지표 (연율화 상수 적용)
        volatility = returns.std() * np.sqrt(annualization_factor) * 100 if len(returns) > 0 else 0
        max_drawdown = PerformanceAnalyzer._calculate_max_drawdown(equity_series)
        
        # 3. 위험 조정 수익률 (연율화 상수 전달)
        sharpe_ratio = PerformanceAnalyzer._calculate_sharpe(returns, annualization_factor=annualization_factor) if len(returns) > 0 else 0
        sortino_ratio = PerformanceAnalyzer._calculate_sortino(returns, annualization_factor=annualization_factor) if len(returns) > 0 else 0
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
        
        # 7. 손실 거래 분석 (P1 #5: 손실 날 메타데이터)
        worst_loss_metadata = PerformanceAnalyzer._analyze_worst_loss_trades(
            trades, losing_trades
        )

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
            'total_commission': sum(t.commission for t in trades),

            # 메타 정보
            'data_interval': data_interval,
            'annualization_factor': annualization_factor,

            # P1 #5: 손실 날 메타데이터 (AI 프롬프트에서 현재 상황과 비교용)
            'worst_loss_metadata': worst_loss_metadata
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
    def _calculate_sharpe(
        returns: pd.Series,
        risk_free_rate: float = 0.02,
        annualization_factor: int = 365
    ) -> float:
        """
        샤프 비율 계산

        Args:
            returns: 수익률 시리즈
            risk_free_rate: 무위험 수익률 (연율, 기본 2%)
            annualization_factor: 연율화 상수 (데이터 간격에 따라 다름)

        Returns:
            연율화된 샤프 비율
        """
        if len(returns) == 0 or returns.std() == 0:
            return 0

        # 무위험 수익률을 데이터 간격에 맞게 조정
        period_risk_free = risk_free_rate / annualization_factor
        excess_returns = returns - period_risk_free

        if excess_returns.std() == 0:
            return 0

        # 연율화된 샤프 비율
        return (excess_returns.mean() / excess_returns.std()) * np.sqrt(annualization_factor)
    
    @staticmethod
    def _calculate_sortino(
        returns: pd.Series,
        risk_free_rate: float = 0.02,
        annualization_factor: int = 365
    ) -> float:
        """
        소르티노 비율 계산 (하방 리스크만 고려)

        Args:
            returns: 수익률 시리즈
            risk_free_rate: 무위험 수익률 (연율, 기본 2%)
            annualization_factor: 연율화 상수 (데이터 간격에 따라 다름)

        Returns:
            연율화된 소르티노 비율
        """
        if len(returns) == 0:
            return 0

        # 무위험 수익률을 데이터 간격에 맞게 조정
        period_risk_free = risk_free_rate / annualization_factor
        excess_returns = returns - period_risk_free
        downside_returns = excess_returns[excess_returns < 0]

        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0

        # 연율화된 소르티노 비율
        return (excess_returns.mean() / downside_returns.std()) * np.sqrt(annualization_factor)
    
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

    @staticmethod
    def _analyze_worst_loss_trades(
        all_trades: List[Trade],
        losing_trades: List[Trade]
    ) -> Dict[str, Any]:
        """
        P1 #5: 손실 거래 분석 - 최악의 손실 거래 메타데이터 추출

        AI 프롬프트에서 현재 시장 상황과 과거 손실 상황을 비교하여
        유사한 환경인지 판단할 수 있도록 메타데이터 제공

        Args:
            all_trades: 모든 거래 목록
            losing_trades: 손실 거래 목록

        Returns:
            손실 거래 메타데이터 딕셔너리
        """
        if not losing_trades:
            return {
                'has_losses': False,
                'message': '손실 거래 없음 (양호)'
            }

        # 최악의 손실 거래 찾기 (금액 기준)
        worst_trade = min(losing_trades, key=lambda t: t.pnl)

        # 손실률 기준 최악 거래
        worst_by_pct = min(
            losing_trades,
            key=lambda t: t.pnl / (t.entry_price * t.size) if t.entry_price and t.size else 0
        )

        # 연속 손실 분석
        consecutive_losses = []
        current_streak = 0
        for trade in all_trades:
            if trade.pnl < 0:
                current_streak += 1
            else:
                if current_streak > 0:
                    consecutive_losses.append(current_streak)
                current_streak = 0
        if current_streak > 0:
            consecutive_losses.append(current_streak)

        max_consecutive = max(consecutive_losses) if consecutive_losses else 0

        # 손실 거래의 평균 보유 기간
        avg_loss_holding_hours = np.mean([
            t.holding_period.total_seconds() / 3600
            for t in losing_trades
        ]) if losing_trades else 0

        # 손실 거래 발생 시간대 분석 (있으면)
        loss_timestamps = []
        for t in losing_trades:
            if hasattr(t, 'exit_time') and t.exit_time:
                loss_timestamps.append(t.exit_time)

        return {
            'has_losses': True,
            'total_loss_count': len(losing_trades),
            'total_loss_amount': sum(t.pnl for t in losing_trades),
            'avg_loss_per_trade': np.mean([t.pnl for t in losing_trades]),

            # 최악의 손실 거래 상세
            'worst_loss': {
                'pnl': worst_trade.pnl,
                'pnl_pct': (worst_trade.pnl / (worst_trade.entry_price * worst_trade.size) * 100)
                    if worst_trade.entry_price and worst_trade.size else 0,
                'entry_price': worst_trade.entry_price,
                'exit_price': worst_trade.exit_price,
                'holding_hours': worst_trade.holding_period.total_seconds() / 3600
                    if hasattr(worst_trade, 'holding_period') else 0,
                'entry_time': str(worst_trade.entry_time) if hasattr(worst_trade, 'entry_time') else None,
                'exit_time': str(worst_trade.exit_time) if hasattr(worst_trade, 'exit_time') else None,
            },

            # 연속 손실 분석
            'max_consecutive_losses': max_consecutive,
            'avg_loss_holding_hours': avg_loss_holding_hours,

            # AI 프롬프트용 경고 메시지
            'warning_message': (
                f"주의: 최악 손실 {worst_trade.pnl:,.0f}원 발생. "
                f"연속 손실 최대 {max_consecutive}회. "
                f"손실 거래 평균 보유: {avg_loss_holding_hours:.1f}시간."
            )
        }




