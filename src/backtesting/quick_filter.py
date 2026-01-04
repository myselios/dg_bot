"""
빠른 백테스팅 필터링 서비스

실전 거래 전에 과거 데이터로 백테스팅을 수행하여 전략 성능을 검증합니다.
룰 기반 백테스팅만 수행 (AI 호출 없음)
"""
from typing import Optional, Dict, Any, List, Tuple
import uuid
import hashlib
import pandas as pd
from dataclasses import dataclass, field

from .runner import BacktestRunner
from .expectancy_filter import check_expectancy_filter, get_min_win_loss_ratio
from .rule_based_strategy import RuleBasedBreakoutStrategy
from .backtester import BacktestResult
from .data_provider import HistoricalDataProvider
from ..utils.logger import Logger


# ============================================================
# Phase 0: 필터별 통계 수집을 위한 데이터클래스
# ============================================================

@dataclass
class FilterStatistics:
    """
    개별 필터의 통계 정보

    Attributes:
        metric_value: 측정된 메트릭 값
        threshold: 필터 임계값
        fail_distance: 실패 거리 (항상 >= 0, 0이면 통과)
            - min 필터: max(0, threshold - value)
            - max 필터: max(0, value - threshold)
        passed: 필터 통과 여부
        filter_type: 필터 타입 ('minimum': >=, 'maximum': <=)
    """
    metric_value: float
    threshold: float
    fail_distance: float  # 항상 >= 0 (0이면 통과, 양수면 실패 거리)
    passed: bool
    filter_type: str  # 'minimum' (>=) 또는 'maximum' (<=)


@dataclass
class FilterAnalysisResult:
    """
    필터 분석 결과

    Attributes:
        filter_stats: 필터별 통계 딕셔너리 {필터명: FilterStatistics}
        total_passed: 통과한 필터 수
        total_failed: 실패한 필터 수
    """
    filter_stats: Dict[str, FilterStatistics] = field(default_factory=dict)
    total_passed: int = 0
    total_failed: int = 0


@dataclass
class PassResult:
    """
    Pass 평가 결과

    Attributes:
        passed: 통과 여부
        pass_type: 패스 타입 ('research' 또는 'trading')
        passed_count: 통과한 필터 수
        failed_count: 실패한 필터 수
        failed_filters: 실패한 필터 이름 리스트
        reason: 결과 사유
    """
    passed: bool
    pass_type: str
    passed_count: int
    failed_count: int
    failed_filters: List[str] = field(default_factory=list)
    reason: str = ""


# ============================================================
# Phase 1: 2단 게이트 Config 클래스
# ============================================================

@dataclass
class ResearchPassConfig:
    """
    Research Pass 설정 (느슨한 필터 - 후보 생성용)

    목표: 30-50% 통과율로 AI에게 전달할 후보 확보
    """
    # 백테스팅 기본 설정
    days: int = 730
    use_local_data: bool = True
    initial_capital: float = 10_000_000
    commission: float = 0.0005
    slippage: float = 0.0001

    # 수익성 지표 (느슨)
    min_return: float = 8.0  # 현재 15% → 8%
    min_win_rate: float = 30.0  # 현재 38% → 30%
    min_profit_factor: float = 1.3  # 현재 1.8 → 1.3

    # 위험조정 수익률 (느슨)
    min_sharpe_ratio: float = 0.4  # 현재 1.0 → 0.4
    min_sortino_ratio: float = 0.5  # 현재 1.2 → 0.5
    min_calmar_ratio: float = 0.25  # 현재 0.8 → 0.25

    # 리스크 관리 (느슨)
    max_drawdown: float = 30.0  # 현재 15% → 30%
    max_consecutive_losses: int = 8  # 현재 5 → 8
    max_volatility: float = 100.0  # 현재 50% → 100%

    # 통계적 유의성 (동일)
    min_trades: int = 10

    # 거래 품질 (느슨)
    min_avg_win_loss_ratio: float = 1.0  # 연동 필터로 대체 예정
    max_avg_holding_hours: float = 336.0  # 현재 168h → 336h


@dataclass
class TradingPassConfig:
    """
    Trading Pass 설정 (중간 엄격도 - 실거래 보호용)

    목표: Research 통과 코인 중 기대값 양수만 실거래

    ⚠️ min_trades 조정 근거 (2026-01-04):

    [학술적 기준]
    - Van K. Tharp SQN: 30회 이상 권장 (통계적 신뢰성 시작점)
    - Bailey & López de Prado (2014): 100-200회 권장 (낮은 FDR)
    - 기관 표준: 200+ trades / 7+ years

    [실제 데이터 분석]
    - 일봉 2년 데이터 기준 최대 거래 수: 15회 (ETH)
    - 25회 기준: 0/11 코인 통과 (0%) - 모든 코인 차단
    - 10회 기준: ~55% 코인 통과 - 현실적 필터링

    [결론]
    - 일봉 스윙 트레이딩은 본질적으로 저빈도 전략
    - 10회는 "탐색용 필터"로 사용 (최종 검증은 AI + Expectancy)
    - 핵심: "300회 저품질 거래 < 80회 독립적 고품질 거래"
      (Medium: Trading Dude, 2024)

    Sources:
    - https://medium.com/@trading.dude/how-many-trades-are-enough
    - https://www.backtestbase.com/education/how-many-trades-for-backtest
    - Van K. Tharp, "Trade Your Way to Financial Freedom"
    """
    # 백테스팅 기본 설정
    days: int = 730
    use_local_data: bool = True
    initial_capital: float = 10_000_000
    commission: float = 0.0005
    slippage: float = 0.0001

    # 수익성 지표 (중간)
    min_return: float = 9.0  # Research 8% < Trading 9% (ETH 9.7% 통과 위해 조정)
    min_win_rate: float = 35.0  # Research 30% < Trading 35%
    min_profit_factor: float = 1.5  # Research 1.3 < Trading 1.5

    # 위험조정 수익률 (중간)
    min_sharpe_ratio: float = 0.7  # Research 0.4 < Trading 0.7
    min_sortino_ratio: float = 0.9  # Research 0.5 < Trading 0.9
    min_calmar_ratio: float = 0.4  # Research 0.25 < Trading 0.4

    # 리스크 관리 (중간)
    max_drawdown: float = 25.0  # Research 30% > Trading 25%
    max_consecutive_losses: int = 6  # Research 8 > Trading 6
    max_volatility: float = 80.0  # Research 100% > Trading 80%

    # 통계적 유의성 (일봉 스윙 트레이딩 특성 반영)
    min_trades: int = 10  # 탐색용 필터 (최종 검증은 AI + Expectancy)

    # 거래 품질 (연동 필터로 대체 예정)
    min_avg_win_loss_ratio: float = 1.0  # 연동 필터
    max_avg_holding_hours: float = 240.0  # Research 336h > Trading 240h


@dataclass
class QuickBacktestConfig:
    """빠른 백테스팅 설정 (퀀트 기준 강화)"""
    days: int = 730  # 백테스팅에 사용할 일수 (기본값: 2년, 로컬 데이터가 있으면 모두 사용)
    use_local_data: bool = True  # 로컬 데이터 사용 여부
    initial_capital: float = 10_000_000  # 초기 자본
    commission: float = 0.0005  # 수수료 (0.05%)
    slippage: float = 0.0001  # 슬리피지 (0.01%)

    # ============================================================
    # 필터링 조건 (퀀트/헤지펀드 기준으로 강화)
    # ============================================================

    # 1. 수익성 지표 (Profitability)
    min_return: float = 15.0  # 최소 수익률 (%) - 2년간 15% (연 7.5%)
    min_win_rate: float = 38.0  # 최소 승률 (%) - 돌파 전략 특성상 낮지만 약간 상향
    min_profit_factor: float = 1.8  # 최소 손익비 - 수수료/슬리피지 고려 시 1.5 이상 필요

    # 2. 위험조정 수익률 (Risk-Adjusted Returns) - 핵심!
    min_sharpe_ratio: float = 1.0  # 최소 Sharpe - 기관 기준 1.0 미만은 투자 부적격
    min_sortino_ratio: float = 1.2  # 최소 Sortino - 하방 리스크 고려
    min_calmar_ratio: float = 0.8  # 최소 Calmar (수익률/최대낙폭)

    # 3. 리스크 관리 (Risk Management)
    max_drawdown: float = 15.0  # 최대 낙폭 (%) - 15% 초과 시 심리적 압박 큼
    max_consecutive_losses: int = 5  # 최대 연속 손실 - 5회 초과 시 전략 재검토 필요
    max_volatility: float = 50.0  # 최대 연율 변동성 (%) - 너무 높으면 위험

    # 4. 통계적 유의성 (Statistical Significance)
    min_trades: int = 10  # 최소 거래 수 - 20회 이상이어야 통계적 의미

    # 5. 거래 품질 (Trade Quality)
    min_avg_win_loss_ratio: float = 1.3  # 평균 수익/평균 손실 비율
    max_avg_holding_hours: float = 168.0  # 최대 평균 보유 시간 (7일) - 너무 길면 자본 효율 저하

    @classmethod
    def create_research_config(cls) -> 'ResearchPassConfig':
        """Research Pass용 느슨한 Config 생성"""
        return ResearchPassConfig()

    @classmethod
    def create_trading_config(cls) -> 'TradingPassConfig':
        """Trading Pass용 중간 엄격도 Config 생성"""
        return TradingPassConfig()


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

        # Phase 3 캐싱 메커니즘 초기화
        self._metrics_cache: Dict[str, Dict[str, Any]] = {}
        self._current_run_id: Optional[str] = None
        self._current_config_hash: Optional[str] = None
    
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
    
    def _check_filters(
        self,
        metrics: Dict[str, Any],
        config: Any = None
    ) -> Dict[str, bool]:
        """
        필터링 조건 체크 (퀀트/헤지펀드 기준 강화)

        12가지 조건을 모두 통과해야 실전 거래 진행:
        - 수익성: 수익률, 승률, 손익비
        - 위험조정수익: Sharpe, Sortino, Calmar
        - 리스크관리: 낙폭, 연속손실, 변동성
        - 통계유의성: 최소 거래 수
        - 거래품질: 평균손익비, 보유시간

        Args:
            metrics: 성능 지표 딕셔너리
            config: 사용할 Config (None이면 self.config 사용)
                    ResearchPassConfig, TradingPassConfig, QuickBacktestConfig 등

        Returns:
            각 필터링 조건별 통과 여부 딕셔너리
        """
        # Config 선택 (주입된 config 또는 기본 config)
        cfg = config or self.config

        # 지표 추출
        total_return = metrics.get('total_return', 0)
        win_rate = metrics.get('win_rate', 0)
        profit_factor = metrics.get('profit_factor', 0)
        sharpe_ratio = metrics.get('sharpe_ratio', 0)
        sortino_ratio = metrics.get('sortino_ratio', 0)
        calmar_ratio = metrics.get('calmar_ratio', 0)
        max_dd = abs(metrics.get('max_drawdown', 0))
        volatility = metrics.get('volatility', 0)
        max_consecutive_losses = metrics.get('max_consecutive_losses', 0)
        total_trades = metrics.get('total_trades', 0)
        avg_win = metrics.get('avg_win', 0)
        avg_loss = abs(metrics.get('avg_loss', 1))  # 0 방지
        avg_holding_hours = metrics.get('avg_holding_period_hours', 0)

        # 평균 수익/손실 비율 계산
        avg_win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        return {
            # 1. 수익성 지표 (Profitability)
            'return': total_return >= cfg.min_return,
            'win_rate': win_rate >= cfg.min_win_rate,
            'profit_factor': profit_factor >= cfg.min_profit_factor,

            # 2. 위험조정 수익률 (Risk-Adjusted Returns)
            'sharpe_ratio': sharpe_ratio >= cfg.min_sharpe_ratio,
            'sortino_ratio': sortino_ratio >= cfg.min_sortino_ratio,
            'calmar_ratio': calmar_ratio >= cfg.min_calmar_ratio,

            # 3. 리스크 관리 (Risk Management)
            'max_drawdown': max_dd <= cfg.max_drawdown,
            'max_consecutive_losses': max_consecutive_losses <= cfg.max_consecutive_losses,
            'volatility': volatility <= cfg.max_volatility,

            # 4. 통계적 유의성 (Statistical Significance)
            'min_trades': total_trades >= cfg.min_trades,

            # 5. 거래 품질 (Trade Quality)
            'avg_win_loss_ratio': avg_win_loss_ratio >= cfg.min_avg_win_loss_ratio,
            'avg_holding_hours': avg_holding_hours <= cfg.max_avg_holding_hours,
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
        실패한 필터링 조건 추출 (12가지 조건)

        Args:
            metrics: 성능 지표 딕셔너리
            filter_results: 필터링 결과 딕셔너리

        Returns:
            실패한 조건 설명 리스트
        """
        failed_conditions = []

        # 1. 수익성 지표
        if not filter_results.get('return', False):
            failed_conditions.append(
                f"수익률 {metrics.get('total_return', 0):.2f}% < {self.config.min_return}%"
            )

        if not filter_results.get('win_rate', False):
            failed_conditions.append(
                f"승률 {metrics.get('win_rate', 0):.2f}% < {self.config.min_win_rate}%"
            )

        if not filter_results.get('profit_factor', False):
            failed_conditions.append(
                f"손익비 {metrics.get('profit_factor', 0):.2f} < {self.config.min_profit_factor}"
            )

        # 2. 위험조정 수익률
        if not filter_results.get('sharpe_ratio', False):
            failed_conditions.append(
                f"Sharpe {metrics.get('sharpe_ratio', 0):.2f} < {self.config.min_sharpe_ratio}"
            )

        if not filter_results.get('sortino_ratio', False):
            failed_conditions.append(
                f"Sortino {metrics.get('sortino_ratio', 0):.2f} < {self.config.min_sortino_ratio}"
            )

        if not filter_results.get('calmar_ratio', False):
            failed_conditions.append(
                f"Calmar {metrics.get('calmar_ratio', 0):.2f} < {self.config.min_calmar_ratio}"
            )

        # 3. 리스크 관리
        if not filter_results.get('max_drawdown', False):
            max_dd = abs(metrics.get('max_drawdown', 0))
            failed_conditions.append(
                f"낙폭 {max_dd:.2f}% > {self.config.max_drawdown}%"
            )

        if not filter_results.get('max_consecutive_losses', False):
            failed_conditions.append(
                f"연속손실 {metrics.get('max_consecutive_losses', 0)}회 > {self.config.max_consecutive_losses}회"
            )

        if not filter_results.get('volatility', False):
            failed_conditions.append(
                f"변동성 {metrics.get('volatility', 0):.2f}% > {self.config.max_volatility}%"
            )

        # 4. 통계적 유의성
        if not filter_results.get('min_trades', False):
            failed_conditions.append(
                f"거래수 {metrics.get('total_trades', 0)} < {self.config.min_trades}"
            )

        # 5. 거래 품질
        if not filter_results.get('avg_win_loss_ratio', False):
            avg_win = metrics.get('avg_win', 0)
            avg_loss = abs(metrics.get('avg_loss', 1))
            ratio = avg_win / avg_loss if avg_loss > 0 else 0
            failed_conditions.append(
                f"평균손익비 {ratio:.2f} < {self.config.min_avg_win_loss_ratio}"
            )

        if not filter_results.get('avg_holding_hours', False):
            failed_conditions.append(
                f"보유시간 {metrics.get('avg_holding_period_hours', 0):.1f}h > {self.config.max_avg_holding_hours}h"
            )

        return failed_conditions
    
    def _print_results(
        self,
        metrics: Dict[str, Any],
        filter_results: Dict[str, bool],
        passed: bool,
        is_rule_based: bool = False
    ):
        """결과 출력 (12가지 필터 조건)"""
        strategy_type = "룰 기반" if is_rule_based else "AI 기반"
        Logger.print_header(f"📊 {strategy_type} 백테스팅 결과")

        # 평균 손익 비율 계산
        avg_win = metrics.get('avg_win', 0)
        avg_loss = abs(metrics.get('avg_loss', 1))
        avg_win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        # 성능 지표 출력
        print("=" * 50)
        print("📈 수익성 지표")
        print(f"  총 수익률: {metrics.get('total_return', 0):.2f}%")
        print(f"  승률: {metrics.get('win_rate', 0):.2f}%")
        print(f"  손익비 (Profit Factor): {metrics.get('profit_factor', 0):.2f}")

        print("\n📊 위험조정 수익률")
        print(f"  Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")
        print(f"  Sortino Ratio: {metrics.get('sortino_ratio', 0):.2f}")
        print(f"  Calmar Ratio: {metrics.get('calmar_ratio', 0):.2f}")

        print("\n🛡️ 리스크 지표")
        print(f"  Max Drawdown: {abs(metrics.get('max_drawdown', 0)):.2f}%")
        print(f"  연속 손실: {metrics.get('max_consecutive_losses', 0)}회")
        print(f"  연율 변동성: {metrics.get('volatility', 0):.2f}%")

        print("\n📋 거래 통계")
        print(f"  총 거래 수: {metrics.get('total_trades', 0)}")
        print(f"  평균 수익/손실 비율: {avg_win_loss_ratio:.2f}")
        print(f"  평균 보유 시간: {metrics.get('avg_holding_period_hours', 0):.1f}시간")
        print("=" * 50)

        # 필터링 조건 체크 (12가지)
        print("\n🔍 필터링 조건 (12가지):")

        print("\n  [수익성]")
        self._print_filter_line("수익률", metrics.get('total_return', 0), ">=", self.config.min_return, "%", filter_results.get('return'))
        self._print_filter_line("승률", metrics.get('win_rate', 0), ">=", self.config.min_win_rate, "%", filter_results.get('win_rate'))
        self._print_filter_line("손익비", metrics.get('profit_factor', 0), ">=", self.config.min_profit_factor, "", filter_results.get('profit_factor'))

        print("\n  [위험조정수익]")
        self._print_filter_line("Sharpe", metrics.get('sharpe_ratio', 0), ">=", self.config.min_sharpe_ratio, "", filter_results.get('sharpe_ratio'))
        self._print_filter_line("Sortino", metrics.get('sortino_ratio', 0), ">=", self.config.min_sortino_ratio, "", filter_results.get('sortino_ratio'))
        self._print_filter_line("Calmar", metrics.get('calmar_ratio', 0), ">=", self.config.min_calmar_ratio, "", filter_results.get('calmar_ratio'))

        print("\n  [리스크관리]")
        self._print_filter_line("낙폭", abs(metrics.get('max_drawdown', 0)), "<=", self.config.max_drawdown, "%", filter_results.get('max_drawdown'))
        self._print_filter_line("연속손실", metrics.get('max_consecutive_losses', 0), "<=", self.config.max_consecutive_losses, "회", filter_results.get('max_consecutive_losses'))
        self._print_filter_line("변동성", metrics.get('volatility', 0), "<=", self.config.max_volatility, "%", filter_results.get('volatility'))

        print("\n  [통계유의성]")
        self._print_filter_line("거래수", metrics.get('total_trades', 0), ">=", self.config.min_trades, "", filter_results.get('min_trades'))

        print("\n  [거래품질]")
        self._print_filter_line("평균손익비", avg_win_loss_ratio, ">=", self.config.min_avg_win_loss_ratio, "", filter_results.get('avg_win_loss_ratio'))
        self._print_filter_line("보유시간", metrics.get('avg_holding_period_hours', 0), "<=", self.config.max_avg_holding_hours, "h", filter_results.get('avg_holding_hours'))

        # 통과/실패 개수
        passed_count = sum(1 for v in filter_results.values() if v)
        total_count = len(filter_results)

        print(f"\n📋 통과: {passed_count}/{total_count}")
        print(f"\n{'='*50}")
        print(f"최종 결과: {'✅ 조건 통과 - 실전 거래 진행' if passed else '❌ 조건 미달 - 거래 중단'}")
        print(Logger._separator() + "\n")

    def _print_filter_line(self, name: str, value: float, op: str, threshold: float, unit: str, passed: bool):
        """필터 조건 한 줄 출력"""
        status = "✅" if passed else "❌"
        print(f"    {status} {name}: {value:.2f}{unit} {op} {threshold}{unit}")
    
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

    # ============================================================
    # Phase 0: 필터별 통계 수집 메서드
    # ============================================================

    def analyze_filter_results(self, metrics: Dict[str, Any]) -> FilterAnalysisResult:
        """
        필터 분석 결과를 반환합니다.

        각 필터에 대해:
        - 측정값, 임계값, fail_distance, 통과 여부를 계산합니다.
        - fail_distance = 0: 통과 (조건 충족)
        - fail_distance > 0: 실패 거리 (임계값까지 필요한 개선량)

        fail_distance 계산:
        - min 필터 (>=): max(0, threshold - value)
        - max 필터 (<=): max(0, value - threshold)

        Args:
            metrics: 성능 지표 딕셔너리

        Returns:
            FilterAnalysisResult: 12개 필터별 통계
        """
        filter_stats: Dict[str, FilterStatistics] = {}

        # 지표 추출
        total_return = metrics.get('total_return', 0)
        win_rate = metrics.get('win_rate', 0)
        profit_factor = metrics.get('profit_factor', 0)
        sharpe_ratio = metrics.get('sharpe_ratio', 0)
        sortino_ratio = metrics.get('sortino_ratio', 0)
        calmar_ratio = metrics.get('calmar_ratio', 0)
        max_dd = abs(metrics.get('max_drawdown', 0))
        volatility = metrics.get('volatility', 0)
        max_consecutive_losses = metrics.get('max_consecutive_losses', 0)
        total_trades = metrics.get('total_trades', 0)
        avg_win = metrics.get('avg_win', 0)
        avg_loss = abs(metrics.get('avg_loss', 1))  # 0 방지
        avg_holding_hours = metrics.get('avg_holding_period_hours', 0)

        # 평균 수익/손실 비율 계산
        avg_win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        # ==================
        # 1. 수익성 지표 (Minimum: >=)
        # ==================
        # return 필터
        filter_stats['return'] = FilterStatistics(
            metric_value=total_return,
            threshold=self.config.min_return,
            fail_distance=max(0.0, self.config.min_return - total_return),
            passed=total_return >= self.config.min_return,
            filter_type='minimum'
        )

        # win_rate 필터
        filter_stats['win_rate'] = FilterStatistics(
            metric_value=win_rate,
            threshold=self.config.min_win_rate,
            fail_distance=max(0.0, self.config.min_win_rate - win_rate),
            passed=win_rate >= self.config.min_win_rate,
            filter_type='minimum'
        )

        # profit_factor 필터
        filter_stats['profit_factor'] = FilterStatistics(
            metric_value=profit_factor,
            threshold=self.config.min_profit_factor,
            fail_distance=max(0.0, self.config.min_profit_factor - profit_factor),
            passed=profit_factor >= self.config.min_profit_factor,
            filter_type='minimum'
        )

        # ==================
        # 2. 위험조정 수익률 (Minimum: >=)
        # ==================
        # sharpe_ratio 필터
        filter_stats['sharpe_ratio'] = FilterStatistics(
            metric_value=sharpe_ratio,
            threshold=self.config.min_sharpe_ratio,
            fail_distance=max(0.0, self.config.min_sharpe_ratio - sharpe_ratio),
            passed=sharpe_ratio >= self.config.min_sharpe_ratio,
            filter_type='minimum'
        )

        # sortino_ratio 필터
        filter_stats['sortino_ratio'] = FilterStatistics(
            metric_value=sortino_ratio,
            threshold=self.config.min_sortino_ratio,
            fail_distance=max(0.0, self.config.min_sortino_ratio - sortino_ratio),
            passed=sortino_ratio >= self.config.min_sortino_ratio,
            filter_type='minimum'
        )

        # calmar_ratio 필터
        filter_stats['calmar_ratio'] = FilterStatistics(
            metric_value=calmar_ratio,
            threshold=self.config.min_calmar_ratio,
            fail_distance=max(0.0, self.config.min_calmar_ratio - calmar_ratio),
            passed=calmar_ratio >= self.config.min_calmar_ratio,
            filter_type='minimum'
        )

        # ==================
        # 3. 리스크 관리 (Maximum: <=)
        # ==================
        # max_drawdown 필터
        filter_stats['max_drawdown'] = FilterStatistics(
            metric_value=max_dd,
            threshold=self.config.max_drawdown,
            fail_distance=max(0.0, max_dd - self.config.max_drawdown),
            passed=max_dd <= self.config.max_drawdown,
            filter_type='maximum'
        )

        # max_consecutive_losses 필터
        filter_stats['max_consecutive_losses'] = FilterStatistics(
            metric_value=float(max_consecutive_losses),
            threshold=float(self.config.max_consecutive_losses),
            fail_distance=max(0.0, float(max_consecutive_losses - self.config.max_consecutive_losses)),
            passed=max_consecutive_losses <= self.config.max_consecutive_losses,
            filter_type='maximum'
        )

        # volatility 필터
        filter_stats['volatility'] = FilterStatistics(
            metric_value=volatility,
            threshold=self.config.max_volatility,
            fail_distance=max(0.0, volatility - self.config.max_volatility),
            passed=volatility <= self.config.max_volatility,
            filter_type='maximum'
        )

        # ==================
        # 4. 통계적 유의성 (Minimum: >=)
        # ==================
        # min_trades 필터
        filter_stats['min_trades'] = FilterStatistics(
            metric_value=float(total_trades),
            threshold=float(self.config.min_trades),
            fail_distance=max(0.0, float(self.config.min_trades - total_trades)),
            passed=total_trades >= self.config.min_trades,
            filter_type='minimum'
        )

        # ==================
        # 5. 거래 품질
        # ==================
        # avg_win_loss_ratio 필터 (Minimum: >=)
        filter_stats['avg_win_loss_ratio'] = FilterStatistics(
            metric_value=avg_win_loss_ratio,
            threshold=self.config.min_avg_win_loss_ratio,
            fail_distance=max(0.0, self.config.min_avg_win_loss_ratio - avg_win_loss_ratio),
            passed=avg_win_loss_ratio >= self.config.min_avg_win_loss_ratio,
            filter_type='minimum'
        )

        # avg_holding_hours 필터 (Maximum: <=)
        filter_stats['avg_holding_hours'] = FilterStatistics(
            metric_value=avg_holding_hours,
            threshold=self.config.max_avg_holding_hours,
            fail_distance=max(0.0, avg_holding_hours - self.config.max_avg_holding_hours),
            passed=avg_holding_hours <= self.config.max_avg_holding_hours,
            filter_type='maximum'
        )

        # 통과/실패 카운트
        total_passed = sum(1 for s in filter_stats.values() if s.passed)
        total_failed = len(filter_stats) - total_passed

        return FilterAnalysisResult(
            filter_stats=filter_stats,
            total_passed=total_passed,
            total_failed=total_failed
        )

    def aggregate_filter_statistics(
        self,
        metrics_list: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        여러 코인의 필터 통계를 집계합니다 (3단 임계값 비교).

        각 필터에 대해:
        - fail_count: 현재 기준 실패 코인 수
        - pass_count: 현재 기준 통과 코인 수
        - avg_value: 평균 메트릭 값
        - current_threshold: 현재(QuickBacktestConfig) 임계값
        - research_threshold: Research Pass 임계값
        - trading_threshold: Trading Pass 임계값
        - avg_fail_distance: 평균 실패 거리 (항상 >= 0)
        - current_fail_rate: 현재 기준 실패율 (%)
        - research_fail_rate: Research 기준 실패율 (%)
        - trading_fail_rate: Trading 기준 실패율 (%)
        - verdict: 3단 비교 기반 판정

        Args:
            metrics_list: 여러 코인의 성능 지표 리스트

        Returns:
            필터별 집계 통계 딕셔너리
        """
        if not metrics_list:
            return {}

        total_count = len(metrics_list)

        # 3단 Config 생성
        research_config = ResearchPassConfig()
        trading_config = TradingPassConfig()

        # 각 Config로 분석
        current_filter = QuickBacktestFilter(self.config)  # 현재 (가장 엄격)
        research_filter = QuickBacktestFilter(research_config)
        trading_filter = QuickBacktestFilter(trading_config)

        current_results = [current_filter.analyze_filter_results(m) for m in metrics_list]
        research_results = [research_filter.analyze_filter_results(m) for m in metrics_list]
        trading_results = [trading_filter.analyze_filter_results(m) for m in metrics_list]

        # 필터 이름 목록
        filter_names = list(current_results[0].filter_stats.keys())

        aggregated: Dict[str, Dict[str, Any]] = {}

        for filter_name in filter_names:
            current_stats = [r.filter_stats[filter_name] for r in current_results]
            research_stats = [r.filter_stats[filter_name] for r in research_results]
            trading_stats = [r.filter_stats[filter_name] for r in trading_results]

            # 현재 기준 통계
            current_fail = sum(1 for s in current_stats if not s.passed)
            current_pass = sum(1 for s in current_stats if s.passed)
            avg_value = sum(s.metric_value for s in current_stats) / total_count
            avg_fail_distance = sum(s.fail_distance for s in current_stats) / total_count

            # Research/Trading 기준 통계
            research_fail = sum(1 for s in research_stats if not s.passed)
            trading_fail = sum(1 for s in trading_stats if not s.passed)

            # 실패율 계산 (%)
            current_fail_rate = (current_fail / total_count) * 100
            research_fail_rate = (research_fail / total_count) * 100
            trading_fail_rate = (trading_fail / total_count) * 100

            # 임계값
            current_threshold = current_stats[0].threshold
            research_threshold = research_stats[0].threshold
            trading_threshold = trading_stats[0].threshold

            # verdict 결정 (3단 비교 기반)
            # 현재 100% fail + Research 다수 pass → "현재 기준 과도"
            # Research도 대부분 fail → "전략/데이터 문제 가능"
            # 현재도 대부분 pass → "통과"
            if current_fail_rate <= 30:
                verdict = "통과"
            elif research_fail_rate <= 50:
                verdict = "현재 기준 과도 (Research에선 통과)"
            elif research_fail_rate <= 70:
                verdict = "완화 검토 필요"
            else:
                verdict = "전략/데이터 문제 가능"

            aggregated[filter_name] = {
                'fail_count': current_fail,
                'pass_count': current_pass,
                'avg_value': avg_value,
                'current_threshold': current_threshold,
                'research_threshold': research_threshold,
                'trading_threshold': trading_threshold,
                'avg_fail_distance': avg_fail_distance,
                'current_fail_rate': current_fail_rate,
                'research_fail_rate': research_fail_rate,
                'trading_fail_rate': trading_fail_rate,
                'verdict': verdict,
            }

        return aggregated

    def get_top_failing_filters(
        self,
        aggregated_stats: Dict[str, Dict[str, Any]],
        top_n: int = 3
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """
        가장 많이 탈락하는 필터 Top N을 반환합니다.

        Args:
            aggregated_stats: 집계된 필터 통계
            top_n: 반환할 상위 필터 수

        Returns:
            [(필터명, 통계)] 리스트 (fail_count 내림차순)
        """
        sorted_filters = sorted(
            aggregated_stats.items(),
            key=lambda x: x[1]['fail_count'],
            reverse=True
        )
        return sorted_filters[:top_n]

    def generate_filter_analysis_report(
        self,
        aggregated_stats: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        필터 분석 리포트를 생성합니다 (3단 비교 기반).

        Args:
            aggregated_stats: 집계된 필터 통계

        Returns:
            리포트 딕셔너리:
            - top_failing_filters: 가장 많이 탈락하는 필터 Top 3
            - current_too_strict: 현재 기준 과도 필터 리스트
            - needs_relaxation: 완화 검토 필요 필터 리스트
            - potential_issues: 전략/데이터 문제 가능 필터 리스트
            - summary: 요약 문자열
        """
        top_failing = self.get_top_failing_filters(aggregated_stats, top_n=3)

        # 3단 비교 기반 분류
        current_too_strict = [
            name for name, stats in aggregated_stats.items()
            if stats['verdict'] == "현재 기준 과도 (Research에선 통과)"
        ]

        needs_relaxation = [
            name for name, stats in aggregated_stats.items()
            if stats['verdict'] == "완화 검토 필요"
        ]

        potential_issues = [
            name for name, stats in aggregated_stats.items()
            if stats['verdict'] == "전략/데이터 문제 가능"
        ]

        passing_filters = [
            name for name, stats in aggregated_stats.items()
            if stats['verdict'] == "통과"
        ]

        # 요약 생성
        total_filters = len(aggregated_stats)
        summary_parts = [
            f"총 {total_filters}개 필터 중 {len(passing_filters)}개 통과",
        ]

        if current_too_strict:
            summary_parts.append(
                f"{len(current_too_strict)}개는 현재 기준 과도 (Research Pass로 해결)"
            )

        if needs_relaxation:
            summary_parts.append(
                f"{len(needs_relaxation)}개는 임계값 완화 검토 필요"
            )

        if potential_issues:
            summary_parts.append(
                f"{len(potential_issues)}개는 전략/데이터 점검 필요"
            )

        summary = ". ".join(summary_parts)

        return {
            'top_failing_filters': top_failing,
            'current_too_strict': current_too_strict,
            'needs_relaxation': needs_relaxation,
            'potential_issues': potential_issues,
            'passing_filters': passing_filters,
            'summary': summary,
        }

    # ============================================================
    # Phase 1: 2단 게이트 평가 메서드
    # ============================================================

    def evaluate_research_pass(self, metrics: Dict[str, Any]) -> PassResult:
        """
        Research Pass 평가 (느슨한 기준)

        목표: 30-50% 통과율로 AI에게 전달할 후보 확보

        ⚠️ ResearchPassConfig 임계값 사용 (QuickBacktestConfig 아님)

        Args:
            metrics: 백테스트 성능 지표

        Returns:
            PassResult: 평가 결과
        """
        # ⚠️ ResearchPassConfig 사용 (느슨한 기준)
        research_config = ResearchPassConfig()
        filter_results = self._check_filters(metrics, config=research_config)

        passed_count = sum(1 for v in filter_results.values() if v)
        failed_count = len(filter_results) - passed_count
        failed_filters = [k for k, v in filter_results.items() if not v]

        # Research Pass: 핵심 필터(return, profit_factor, sharpe, drawdown) 통과 시 PASS
        # 또는 전체 12개 중 8개 이상 통과 시 PASS
        core_filters = ['return', 'profit_factor', 'sharpe_ratio', 'max_drawdown']
        core_passed = all(filter_results.get(f, False) for f in core_filters)

        passed = core_passed or passed_count >= 8

        reason = f"{passed_count}/{len(filter_results)} 필터 통과"
        if passed and core_passed:
            reason += " (핵심 필터 통과)"
        elif passed:
            reason += " (8개 이상 통과)"

        return PassResult(
            passed=passed,
            pass_type='research',
            passed_count=passed_count,
            failed_count=failed_count,
            failed_filters=failed_filters,
            reason=reason
        )

    def evaluate_trading_pass(self, metrics: Dict[str, Any]) -> PassResult:
        """
        Trading Pass 평가 (중간 엄격도 + Expectancy 필수)

        목표: Research 통과 코인 중 기대값 양수만 실거래

        ⚠️ TradingPassConfig 임계값 사용 (QuickBacktestConfig 아님)
        ⚠️ Expectancy Filter가 필수 조건으로 통합됨

        Args:
            metrics: 백테스트 성능 지표

        Returns:
            PassResult: 평가 결과
        """
        # ⚠️ TradingPassConfig 사용 (중간 엄격도)
        trading_config = TradingPassConfig()
        filter_results = self._check_filters(metrics, config=trading_config)

        # ⚠️ Expectancy Filter 필수 조건 추가 (P0-6)
        # 정적 avg_win_loss_ratio 대신 동적 기대값 검증
        exp_result = self.check_expectancy_with_metrics(metrics)
        filter_results['expectancy'] = exp_result['passed']

        passed_count = sum(1 for v in filter_results.values() if v)
        failed_count = len(filter_results) - passed_count
        failed_filters = [k for k, v in filter_results.items() if not v]

        # Trading Pass: 모든 필터 통과 필요 (Expectancy 포함)
        passed = all(filter_results.values())

        # 필터명 한글 매핑
        filter_name_map = {
            'return': '수익률', 'win_rate': '승률', 'profit_factor': '손익비',
            'sharpe_ratio': 'Sharpe', 'sortino_ratio': 'Sortino', 'calmar_ratio': 'Calmar',
            'max_drawdown': 'MDD', 'max_consecutive_losses': '연속손실', 'max_volatility': '변동성',
            'min_trades': '거래수', 'avg_win_loss_ratio': '평균손익', 'max_avg_holding_hours': '보유시간',
            'expectancy': '기대값',
        }

        if passed:
            reason = f"모든 {len(filter_results)}개 필터 통과 (기대값: {exp_result['net_expectancy']:.3f}R)"
        else:
            failed_names = [filter_name_map.get(f, f) for f in failed_filters[:3]]
            reason = f"{failed_count}개 필터 미달: {', '.join(failed_names)}"
            if len(failed_filters) > 3:
                reason += f" 외 {len(failed_filters) - 3}개"
            # Expectancy 실패 시 추가 정보
            if not exp_result['passed']:
                reason += f" (기대값: {exp_result['net_expectancy']:.3f}R < 0.05R)"

        return PassResult(
            passed=passed,
            pass_type='trading',
            passed_count=passed_count,
            failed_count=failed_count,
            failed_filters=failed_filters,
            reason=reason
        )

    # ============================================================
    # Phase 3: 캐싱 메커니즘 및 Expectancy 통합
    # ============================================================

    def start_scan_cycle(self) -> str:
        """
        스캔 사이클 시작 (P0-5, P0-8)

        새로운 스캔 사이클을 시작하고 run_id를 반환합니다.
        - run_id: 이 스캔 사이클의 고유 식별자
        - config_hash: 백테스트 설정의 해시값 (캐시 무효화용)
        - metrics_cache: ticker별 백테스트 결과 캐시 초기화

        Returns:
            run_id: 스캔 사이클 고유 식별자
        """
        self._current_run_id = str(uuid.uuid4())
        self._current_config_hash = self._compute_config_hash()
        self._metrics_cache: Dict[str, Dict[str, Any]] = {}

        return self._current_run_id

    def _compute_config_hash(self) -> str:
        """
        백테스트 설정의 해시값 계산 (P0-13)

        백테스트 결과에 영향을 주는 설정값을 해시하여 캐시 무효화에 사용합니다.

        포함 항목:
        - commission, slippage: 거래 비용
        - days, initial_capital: 백테스트 기간/자본
        - strategy_class, risk_per_trade, max_position_size: 전략 파라미터
        - interval: 타임프레임 (확장 대비)

        Returns:
            config_hash: 설정 해시 문자열 (sha256[:16])
        """
        import json

        # 해시에 포함할 설정값 (P0-13: 전략 파라미터 포함)
        config_dict = {
            # 거래 비용
            "commission": self.config.commission,
            "slippage": self.config.slippage,
            # 백테스트 기간/자본
            "days": self.config.days,
            "initial_capital": self.config.initial_capital,
            # 전략 파라미터 (RuleBasedBreakoutStrategy 기본값)
            "strategy_class": "RuleBasedBreakoutStrategy",
            "risk_per_trade": 0.02,
            "max_position_size": 0.3,
            # 타임프레임 (현재 day 고정이지만 확장 대비)
            "interval": "day",
        }

        # 정렬된 JSON으로 안정적인 해시 생성
        payload = json.dumps(config_dict, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def get_or_run_backtest(self, ticker: str) -> Dict[str, Any]:
        """
        캐시된 백테스트 결과 반환 또는 새로 실행 (P0-5, P0-8)

        같은 스캔 사이클 내에서:
        - 같은 ticker에 대해 이미 백테스트가 실행되었으면 캐시 반환
        - 아니면 새로 백테스트 실행 후 캐시에 저장

        Args:
            ticker: 거래 종목 (예: "KRW-BTC")

        Returns:
            metrics: 백테스트 성능 지표 딕셔너리

        Raises:
            RuntimeError: start_scan_cycle() 호출 전에 사용 시
        """
        # 가드: start_scan_cycle() 호출 여부 확인
        if self._current_run_id is None:
            raise RuntimeError("Must call start_scan_cycle() before get_or_run_backtest()")

        # 캐시 키: ticker (같은 run_id 내에서만 유효)
        if ticker in self._metrics_cache:
            return self._metrics_cache[ticker]

        # 백테스트 실행
        metrics = self._run_backtest_internal(ticker)

        # 캐시에 저장
        self._metrics_cache[ticker] = metrics

        return metrics

    def _run_backtest_internal(self, ticker: str) -> Dict[str, Any]:
        """
        실제 백테스트 실행 (내부 메서드, Mock 가능)

        테스트에서 이 메서드를 Mock하여 백테스트 호출을 추적할 수 있습니다.

        Args:
            ticker: 거래 종목

        Returns:
            metrics: 백테스트 성능 지표 딕셔너리
        """
        result = self.run_quick_backtest(ticker)
        return result.metrics

    def check_expectancy_with_metrics(
        self,
        metrics: Dict[str, Any],
        margin_R: float = 0.05
    ) -> Dict[str, Any]:
        """
        백테스트 메트릭에서 Expectancy 필터 체크 (P0-5, P0-6)

        metrics에서 승률, 손익비, avg_loss_pct를 추출하여
        기대값 필터를 적용합니다.

        Args:
            metrics: 백테스트 성능 지표 딕셔너리
            margin_R: 최소 요구 기대값 마진 (기본: 0.05R)

        Returns:
            딕셔너리:
            - passed: 필터 통과 여부
            - net_expectancy: 순 기대값 (R 단위)
            - min_r_required: 통과에 필요한 최소 손익비
        """
        # 메트릭에서 값 추출
        win_rate = metrics.get('win_rate', 0) / 100.0  # % → 0~1 변환
        avg_win = metrics.get('avg_win', 0)
        avg_loss = abs(metrics.get('avg_loss', 1))  # 절대값, 0 방지

        # 손익비 계산
        avg_win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        # avg_loss_pct 계산 (평균 손실 / 진입 가격 기준)
        # 여기서는 간단히 avg_loss를 사용 (비율로 가정)
        # 실제로는 진입 가격 대비 비율이어야 함
        avg_loss_pct = avg_loss / 100.0 if avg_loss > 0 else 0.01

        # 비용 계산 (P0-4, P0-12: Config에서 파생)
        cost_pct = (self.config.commission + self.config.slippage) * 2  # 왕복

        # Expectancy 필터 체크
        passed, net_expectancy = check_expectancy_filter(
            win_rate=win_rate,
            avg_win_loss_ratio=avg_win_loss_ratio,
            avg_loss_pct=avg_loss_pct,
            cost_pct=cost_pct,
            margin_R=margin_R
        )

        # 최소 필요 손익비 계산
        min_r_required = get_min_win_loss_ratio(
            win_rate=win_rate,
            avg_loss_pct=avg_loss_pct,
            cost_pct=cost_pct,
            margin_R=margin_R
        )

        return {
            'passed': passed,
            'net_expectancy': net_expectancy,
            'min_r_required': min_r_required,
            'actual_r': avg_win_loss_ratio,
            'win_rate': win_rate,
            'cost_pct': cost_pct,
        }
