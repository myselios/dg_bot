"""
빠른 백테스팅 필터링 서비스

실전 거래 전에 과거 데이터로 백테스팅을 수행하여 전략 성능을 검증합니다.
룰 기반 백테스팅만 수행 (AI 호출 없음)
"""
from typing import Optional, Dict, Any, List, Tuple
import pandas as pd
from dataclasses import dataclass

from .runner import BacktestRunner
from .rule_based_strategy import RuleBasedBreakoutStrategy
from .backtester import BacktestResult
from .data_provider import HistoricalDataProvider
from ..utils.logger import Logger


@dataclass
class QuickBacktestConfig:
    """빠른 백테스팅 설정"""
    days: int = 730  # 백테스팅에 사용할 일수 (기본값: 2년, 로컬 데이터가 있으면 모두 사용)
    use_local_data: bool = True  # 로컬 데이터 사용 여부
    initial_capital: float = 10_000_000  # 초기 자본
    commission: float = 0.0005  # 수수료 (0.05%)
    slippage: float = 0.0001  # 슬리피지 (0.01%)
    
    # 룰 기반 필터링 조건 (변동성 돌파 전략 특성 반영)
    # 돌파 매매는 승률이 낮아도 손익비로 먹는 전략이므로 승률 기준 완화
    min_return: float = 3.0  # 최소 수익률 (%)
    min_win_rate: float = 35.0  # 최소 승률 (%) - 돌파 전략 특성상 낮음
    min_profit_factor: float = 1.3  # 최소 손익비 (Profit Factor)
    min_sharpe_ratio: float = 0.8  # 최소 Sharpe Ratio
    max_drawdown: float = 20.0  # 최대 낙폭 (%) - 돌파 전략 특성상 높음
    min_trades: int = 3  # 최소 거래 수 (통계적 유의성)


@dataclass
class QuickBacktestResult:
    """빠른 백테스팅 결과"""
    passed: bool  # 필터링 조건 통과 여부
    result: Optional[BacktestResult]  # 백테스트 결과 (룰 기반 또는 AI 기반)
    metrics: Dict[str, Any]  # 성능 지표
    filter_results: Dict[str, bool]  # 각 필터링 조건별 통과 여부
    reason: str  # 통과/실패 사유
    rule_based_result: Optional[BacktestResult] = None  # 룰 기반 백테스트 결과
    ai_result: Optional[BacktestResult] = None  # AI 기반 백테스트 결과 (룰 통과 시)
    # 타임프레임별 결과
    daily_result: Optional[BacktestResult] = None  # 일봉 백테스트 결과
    hourly_result: Optional[BacktestResult] = None  # 시봉 백테스트 결과
    minute_result: Optional[BacktestResult] = None  # 분봉 백테스트 결과
    daily_passed: bool = False  # 일봉 필터링 통과 여부
    hourly_passed: bool = False  # 시봉 필터링 통과 여부
    minute_passed: bool = False  # 분봉 필터링 통과 여부


class QuickBacktestFilter:
    """빠른 백테스팅 필터링 클래스"""
    
    def __init__(self, config: Optional[QuickBacktestConfig] = None):
        """
        Args:
            config: 빠른 백테스팅 설정 (None이면 기본값 사용)
        """
        self.config = config or QuickBacktestConfig()
        self.data_provider = HistoricalDataProvider()
    
    def run_quick_backtest(
        self,
        ticker: str,
        chart_data: Optional[Dict[str, pd.DataFrame]] = None
    ) -> QuickBacktestResult:
        """
        빠른 백테스팅 실행 및 필터링
        일봉 데이터로 백테스트를 실행하여 전략 성능을 검증합니다.
        
        Args:
            ticker: 거래 종목
            chart_data: 차트 데이터 (day, minute60, minute15) - 선택적
                       None이면 로컬 데이터를 사용하여 1년치 데이터 로드
            
        Returns:
            QuickBacktestResult: 빠른 백테스팅 결과
        """
        Logger.print_header(f"⚡ 빠른 백테스팅 필터링 ({self.config.days}일)")
        
        try:
            # 1. 데이터 로드
            if self.config.use_local_data and chart_data is None:
                # 로컬 데이터 사용 (모든 연도 데이터 자동 로드)
                Logger.print_info(f"로컬 데이터에서 모든 연도 데이터 로드 중...")
                df_day = self.data_provider.load_historical_data(
                    ticker=ticker,
                    days=self.config.days,
                    interval="day",
                    use_cache=True
                )
                
                if df_day is None or len(df_day) == 0:
                    return QuickBacktestResult(
                        passed=False,
                        result=None,
                        metrics={},
                        filter_results={},
                        reason="로컬 데이터를 로드할 수 없습니다."
                    )
            else:
                # 기존 방식: chart_data에서 추출
                if chart_data is None:
                    return QuickBacktestResult(
                        passed=False,
                        result=None,
                        metrics={},
                        filter_results={},
                        reason="차트 데이터가 없습니다."
                    )
                
                df_day = chart_data.get('day')
                if df_day is None or len(df_day) == 0:
                    return QuickBacktestResult(
                        passed=False,
                        result=None,
                        metrics={},
                        filter_results={},
                        reason="차트 데이터가 없습니다."
                    )
                
                # 최근 N일 데이터만 사용
                df_day = df_day.tail(self.config.days).copy()
            
            # 데이터 검증
            if len(df_day) < 10:
                return QuickBacktestResult(
                    passed=False,
                    result=None,
                    metrics={},
                    filter_results={},
                    reason=f"데이터가 부족합니다 (최소 10일 필요, 현재: {len(df_day)}일)"
                )
            
            Logger.print_info(f"백테스팅 데이터: {len(df_day)}일 (기간: {df_day.index[0]} ~ {df_day.index[-1]})")
            
            # 백테스팅에 사용할 데이터
            backtest_data = df_day.copy()
            
            # ============================================
            # 룰 기반 백테스팅 (AI 호출 없음)
            # ============================================
            Logger.print_header("🔍 룰 기반 백테스팅 (변동성 돌파 전략)")
            Logger.print_info("AI 호출 없이 3단계 관문 룰만으로 백테스팅 실행 중...")
            
            rule_strategy = RuleBasedBreakoutStrategy(
                ticker=ticker,
                risk_per_trade=0.02,
                max_position_size=0.3
            )
            
            rule_backtest_result = BacktestRunner.run_backtest(
                strategy=rule_strategy,
                data=backtest_data,
                ticker=ticker,
                initial_capital=self.config.initial_capital,
                commission=self.config.commission,
                slippage=self.config.slippage
            )
            
            rule_metrics = rule_backtest_result.metrics
            
            # 룰 기반 결과 출력
            self._print_metrics_summary(rule_metrics, "룰 기반")
            
            # 룰 기반 필터링 조건 체크
            rule_filter_results = self._check_filters(rule_metrics)
            rule_passed = all(rule_filter_results.values())
            
            reason = self._generate_reason(rule_metrics, rule_filter_results, rule_passed)
            
            # 결과 출력
            self._print_results(rule_metrics, rule_filter_results, rule_passed, is_rule_based=True)
            
            return QuickBacktestResult(
                passed=rule_passed,
                result=rule_backtest_result,
                metrics=rule_metrics,
                filter_results=rule_filter_results,
                reason=reason,
                rule_based_result=rule_backtest_result
            )
            
        except Exception as e:
            Logger.print_error(f"빠른 백테스팅 실패: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return QuickBacktestResult(
                passed=False,
                result=None,
                metrics={},
                filter_results={},
                reason=f"백테스팅 실행 중 오류 발생: {str(e)}"
            )
    
    def _load_timeframe_data(
        self,
        ticker: str,
        interval: str,
        chart_data: Optional[Dict[str, pd.DataFrame]]
    ) -> Optional[pd.DataFrame]:
        """
        타임프레임별 데이터 로드
        
        Args:
            ticker: 거래 종목
            interval: 시간 간격 ('day', 'minute60', 'minute15')
            chart_data: 차트 데이터 (선택적)
            
        Returns:
            DataFrame 또는 None
        """
        if self.config.use_local_data and chart_data is None:
            # 로컬 데이터 사용
            df = self.data_provider.load_historical_data(
                ticker=ticker,
                days=self.config.days,
                interval=interval,
                use_cache=True
            )
            return df
        else:
            # 기존 방식: chart_data에서 추출
            if chart_data is None:
                return None
            
            # interval에 따라 chart_data 키 매핑
            key_map = {
                "day": "day",
                "minute60": "minute60",
                "minute15": "minute15"
            }
            
            key = key_map.get(interval)
            if key is None:
                return None
            
            df = chart_data.get(key)
            if df is None or len(df) == 0:
                return None
            
            # 최근 N일 데이터만 사용 (일봉 기준으로 계산)
            if interval == "day":
                return df.tail(self.config.days).copy()
            elif interval == "minute60":
                # 시봉: 일봉의 약 24배 데이터
                return df.tail(self.config.days * 24).copy()
            elif interval == "minute15":
                # 분봉: 일봉의 약 96배 데이터
                return df.tail(self.config.days * 96).copy()
            
            return df
    
    def _run_single_backtest(
        self,
        ticker: str,
        data: pd.DataFrame,
        timeframe_name: str
    ) -> Tuple[Optional[BacktestResult], bool, str]:
        """
        단일 타임프레임 백테스트 실행
        
        Args:
            ticker: 거래 종목
            data: 백테스트 데이터
            timeframe_name: 타임프레임 이름 (출력용)
            
        Returns:
            (백테스트 결과, 통과 여부, 사유)
        """
        if len(data) < 10:
            return None, False, f"데이터가 부족합니다 (최소 10개 필요, 현재: {len(data)}개)"
        
        Logger.print_info(f"{timeframe_name} 데이터: {len(data)}개 (기간: {data.index[0]} ~ {data.index[-1]})")
        
        # 룰 기반 백테스팅
        rule_strategy = RuleBasedBreakoutStrategy(
            ticker=ticker,
            risk_per_trade=0.02,
            max_position_size=0.3
        )
        
        rule_backtest_result = BacktestRunner.run_backtest(
            strategy=rule_strategy,
            data=data,
            ticker=ticker,
            initial_capital=self.config.initial_capital,
            commission=self.config.commission,
            slippage=self.config.slippage
        )
        
        rule_metrics = rule_backtest_result.metrics
        self._print_metrics_summary(rule_metrics, f"{timeframe_name} 룰 기반")
        
        # 필터링 조건 체크
        filter_results = self._check_filters(rule_metrics)
        passed = all(filter_results.values())
        reason = self._generate_reason(rule_metrics, filter_results, passed)
        
        self._print_results(rule_metrics, filter_results, passed, is_rule_based=True)
        
        return rule_backtest_result, passed, reason
    
    def _check_filters(self, metrics: Dict[str, Any]) -> Dict[str, bool]:
        """
        필터링 조건 체크 (변동성 돌파 전략 특성 반영)
        
        돌파 매매는 승률이 낮아도 손익비로 수익을 내는 전략이므로:
        - 승률 기준 완화 (35%)
        - 손익비 강화 (1.3 이상)
        - 최대 낙폭 허용 범위 확대 (20%)
        
        Args:
            metrics: 성능 지표 딕셔너리
            
        Returns:
            각 필터링 조건별 통과 여부 딕셔너리
        """
        total_return = metrics.get('total_return', 0)
        win_rate = metrics.get('win_rate', 0)
        profit_factor = metrics.get('profit_factor', 0)
        sharpe_ratio = metrics.get('sharpe_ratio', 0)
        max_dd = abs(metrics.get('max_drawdown', 0))  # 음수이므로 절댓값 사용
        total_trades = metrics.get('total_trades', 0)
        
        return {
            'return': total_return >= self.config.min_return,
            'win_rate': win_rate >= self.config.min_win_rate,
            'profit_factor': profit_factor >= self.config.min_profit_factor,
            'sharpe_ratio': sharpe_ratio >= self.config.min_sharpe_ratio,
            'max_drawdown': max_dd <= self.config.max_drawdown,
            'min_trades': total_trades >= self.config.min_trades
        }
    
    def _generate_reason(
        self,
        metrics: Dict[str, Any],
        filter_results: Dict[str, bool],
        passed: bool
    ) -> str:
        """
        통과/실패 사유 생성
        
        Args:
            metrics: 성능 지표 딕셔너리
            filter_results: 필터링 결과 딕셔너리
            passed: 통과 여부
            
        Returns:
            사유 문자열
        """
        if passed:
            return "모든 필터링 조건을 통과했습니다."
        
        failed_conditions = self._extract_failed_conditions(metrics, filter_results)
        return f"필터링 조건 미달: {', '.join(failed_conditions)}"
    
    def _extract_failed_conditions(
        self,
        metrics: Dict[str, Any],
        filter_results: Dict[str, bool]
    ) -> List[str]:
        """
        실패한 필터링 조건 추출
        
        Args:
            metrics: 성능 지표 딕셔너리
            filter_results: 필터링 결과 딕셔너리
            
        Returns:
            실패한 조건 설명 리스트
        """
        failed_conditions = []
        
        if not filter_results.get('return', False):
            failed_conditions.append(
                f"수익률 {metrics.get('total_return', 0):.2f}% < {self.config.min_return}%"
            )
        
        if not filter_results.get('win_rate', False):
            failed_conditions.append(
                f"승률 {metrics.get('win_rate', 0):.2f}% < {self.config.min_win_rate}%"
            )
        
        if not filter_results.get('sharpe_ratio', False):
            failed_conditions.append(
                f"Sharpe Ratio {metrics.get('sharpe_ratio', 0):.2f} < {self.config.min_sharpe_ratio}"
            )
        
        if not filter_results.get('max_drawdown', False):
            max_dd = abs(metrics.get('max_drawdown', 0))
            failed_conditions.append(
                f"Max Drawdown {max_dd:.2f}% > {self.config.max_drawdown}%"
            )
        
        if not filter_results.get('profit_factor', False):
            profit_factor = metrics.get('profit_factor', 0)
            failed_conditions.append(
                f"Profit Factor {profit_factor:.2f} < {self.config.min_profit_factor}"
            )
        
        if not filter_results.get('min_trades', False):
            total_trades = metrics.get('total_trades', 0)
            failed_conditions.append(
                f"총 거래 수 {total_trades} < {self.config.min_trades}"
            )
        
        return failed_conditions
    
    def _print_results(
        self,
        metrics: Dict[str, Any],
        filter_results: Dict[str, bool],
        passed: bool,
        is_rule_based: bool = False
    ):
        """결과 출력"""
        strategy_type = "룰 기반" if is_rule_based else "AI 기반"
        Logger.print_header(f"📊 {strategy_type} 백테스팅 결과")
        
        # 성능 지표 출력
        print(f"총 수익률: {metrics.get('total_return', 0):.2f}%")
        print(f"승률: {metrics.get('win_rate', 0):.2f}%")
        print(f"손익비: {metrics.get('profit_factor', 0):.2f}")
        print(f"Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")
        print(f"Max Drawdown: {abs(metrics.get('max_drawdown', 0)):.2f}%")
        print(f"총 거래 수: {metrics.get('total_trades', 0)}")
        
        print("\n필터링 조건:")
        print(f"  ✅ 수익률 > {self.config.min_return}%: {'✅ 통과' if filter_results.get('return') else '❌ 실패'}")
        print(f"  ✅ 승률 > {self.config.min_win_rate}%: {'✅ 통과' if filter_results.get('win_rate') else '❌ 실패'}")
        print(f"  ✅ 손익비 > {self.config.min_profit_factor}: {'✅ 통과' if filter_results.get('profit_factor') else '❌ 실패'}")
        print(f"  ✅ Sharpe Ratio > {self.config.min_sharpe_ratio}: {'✅ 통과' if filter_results.get('sharpe_ratio') else '❌ 실패'}")
        print(f"  ✅ Max Drawdown < {self.config.max_drawdown}%: {'✅ 통과' if filter_results.get('max_drawdown') else '❌ 실패'}")
        print(f"  ✅ 최소 거래 수 > {self.config.min_trades}: {'✅ 통과' if filter_results.get('min_trades') else '❌ 실패'}")
        
        print(f"\n최종 결과: {'✅ 조건 통과 - 실전 거래 진행' if passed else '❌ 조건 미달 - 거래 중단'}")
        print(Logger._separator() + "\n")
    
    def _print_metrics_summary(self, metrics: Dict[str, Any], strategy_type: str) -> None:
        """
        성능 지표 요약 출력
        
        Args:
            metrics: 성능 지표 딕셔너리
            strategy_type: 전략 타입 ("룰 기반" 또는 "AI 기반")
        """
        Logger.print_info(f"📊 {strategy_type} 백테스팅 결과:")
        Logger.print_info(f"  - 총 수익률: {metrics.get('total_return', 0):.2f}%")
        Logger.print_info(f"  - 승률: {metrics.get('win_rate', 0):.2f}%")
        Logger.print_info(f"  - 손익비: {metrics.get('profit_factor', 0):.2f}")
        Logger.print_info(f"  - Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")
        Logger.print_info(f"  - Max Drawdown: {abs(metrics.get('max_drawdown', 0)):.2f}%")
        Logger.print_info(f"  - 총 거래 수: {metrics.get('total_trades', 0)}")

