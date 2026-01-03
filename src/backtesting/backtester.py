"""
백테스팅 엔진

Clean Architecture 통합:
- ExecutionPort를 통한 체결 시뮬레이션
- use_intrabar_stops 옵션으로 현실적인 스탑/익절 시뮬레이션
"""
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import pandas as pd

from .strategy import Strategy
from .portfolio import Portfolio
from src.application.ports.outbound.execution_port import (
    ExecutionPort,
    CandleData,
)
from src.infrastructure.adapters.execution import (
    SimpleExecutionAdapter,
    IntrabarExecutionAdapter,
)
from src.domain.value_objects import Money


@dataclass
class BacktestResult:
    """백테스트 결과"""
    initial_capital: float
    final_equity: float
    equity_curve: List[float]
    trades: List
    metrics: dict
    execution_mode: str = 'close'  # 'close' 또는 'next_open'


class Backtester:
    """
    백테스팅 엔진
    """
    
    def __init__(
        self,
        strategy: Strategy,           # 거래 전략
        data: pd.DataFrame,           # 과거 데이터
        ticker: str,                  # 거래 종목
        initial_capital: float,       # 초기 자본
        commission: float = 0.0005,   # 수수료 (0.05%)
        slippage: float = 0.0001,     # 슬리피지 (0.01%)
        slippage_model: dict = None,  # 슬리피지 모델 (오더북 기반)
        use_split_orders: bool = False,  # 분할 주문 사용 여부
        execute_on_next_open: bool = True,  # True: 다음 봉 시가 체결 (현실적), False: 현재 봉 종가 체결
        data_interval: str = 'day',   # 데이터 간격 ('day', 'minute60', 'minute15', 등) - 연율화 계산용
        use_intrabar_stops: bool = False,  # True: 봉 내 스탑/익절 체크 (현실적), False: 종가 기준
        execution_adapter: Optional[ExecutionPort] = None  # 커스텀 어댑터 (테스트용)
    ):
        self.strategy = strategy
        self.data = data
        self.ticker = ticker
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.use_split_orders = use_split_orders
        self.execute_on_next_open = execute_on_next_open  # Look-Ahead Bias 방지 옵션
        self.data_interval = data_interval  # 데이터 간격 (성과 지표 연율화용)
        self.use_intrabar_stops = use_intrabar_stops  # 봉 내 스탑/익절 체크 옵션

        # ExecutionPort 어댑터 설정
        if execution_adapter is not None:
            self._execution_adapter = execution_adapter
        elif use_intrabar_stops:
            self._execution_adapter = IntrabarExecutionAdapter()
        else:
            self._execution_adapter = SimpleExecutionAdapter()

        # 슬리피지 모델 설정
        if slippage_model is None:
            self.slippage_model = {
                'type': 'percentage',
                'buy_slippage': slippage,
                'sell_slippage': slippage
            }
        else:
            self.slippage_model = slippage_model

        # 상태 관리
        self.portfolio = Portfolio(initial_capital)
        self.orders = []
        self.trades = []
        self.equity_curve = []
        self.slippage_statistics = []  # 슬리피지 통계

        # 현재 포지션의 스탑/익절 가격 추적
        self._current_stop_loss: Optional[float] = None
        self._current_take_profit: Optional[float] = None
        self._current_entry_price: Optional[float] = None

    def _create_candle_data(self, bar: pd.Series) -> CandleData:
        """pandas Series를 CandleData로 변환"""
        timestamp = bar.name if isinstance(bar.name, datetime) else datetime.now()
        return CandleData(
            timestamp=timestamp,
            open=Money.krw(Decimal(str(bar['open']))),
            high=Money.krw(Decimal(str(bar['high']))),
            low=Money.krw(Decimal(str(bar['low']))),
            close=Money.krw(Decimal(str(bar['close']))),
            volume=Decimal(str(bar.get('volume', 0)))
        )

    def _check_intrabar_exit(self, current_bar: pd.Series) -> bool:
        """
        봉 내 스탑/익절 체크

        Returns:
            bool: 청산 발생 여부
        """
        # 포지션 없으면 체크 불필요
        position = self.portfolio.positions.get(self.ticker)
        if not position or position.size <= 0:
            return False

        # 스탑/익절 가격 없으면 체크 불필요
        if self._current_stop_loss is None and self._current_take_profit is None:
            return False

        candle = self._create_candle_data(current_bar)

        # 스탑 체크
        stop_triggered = False
        if self._current_stop_loss is not None:
            stop_price = Money.krw(Decimal(str(self._current_stop_loss)))
            stop_triggered = self._execution_adapter.check_stop_loss_triggered(
                stop_price, candle
            )

        # 익절 체크
        tp_triggered = False
        if self._current_take_profit is not None:
            tp_price = Money.krw(Decimal(str(self._current_take_profit)))
            tp_triggered = self._execution_adapter.check_take_profit_triggered(
                tp_price, candle
            )

        if not stop_triggered and not tp_triggered:
            return False

        # 청산 가격 결정
        if stop_triggered and tp_triggered:
            # 둘 다 트리거된 경우 - IntrabarExecutionAdapter는 worst-case 가정
            if hasattr(self._execution_adapter, 'get_exit_priority'):
                stop_price = Money.krw(Decimal(str(self._current_stop_loss)))
                tp_price = Money.krw(Decimal(str(self._current_take_profit)))
                priority = self._execution_adapter.get_exit_priority(
                    stop_price, tp_price, candle
                )
                if priority == "stop_loss":
                    exit_price = self._execution_adapter.get_stop_loss_execution_price(
                        stop_price, candle
                    )
                    exit_reason = "stop_loss"
                else:
                    exit_price = self._execution_adapter.get_take_profit_execution_price(
                        tp_price, candle
                    )
                    exit_reason = "take_profit"
            else:
                # 기본: 스탑 우선 (worst-case)
                stop_price = Money.krw(Decimal(str(self._current_stop_loss)))
                exit_price = self._execution_adapter.get_stop_loss_execution_price(
                    stop_price, candle
                )
                exit_reason = "stop_loss"
        elif stop_triggered:
            stop_price = Money.krw(Decimal(str(self._current_stop_loss)))
            exit_price = self._execution_adapter.get_stop_loss_execution_price(
                stop_price, candle
            )
            exit_reason = "stop_loss"
        else:  # tp_triggered
            tp_price = Money.krw(Decimal(str(self._current_take_profit)))
            exit_price = self._execution_adapter.get_take_profit_execution_price(
                tp_price, candle
            )
            exit_reason = "take_profit"

        # 청산 실행
        exit_price_float = float(exit_price.amount)
        trade = self.portfolio.close_position(
            symbol=self.ticker,
            price=exit_price_float,
            commission=self.commission,
            slippage=0  # 이미 ExecutionPort에서 처리
        )

        if trade:
            self.trades.append(trade)
            self.orders.append({
                'action': 'sell',
                'price': exit_price_float,
                'actual_price': exit_price_float,
                'size': trade.size,
                'timestamp': current_bar.name,
                'exit_reason': exit_reason,
                'intrabar_exit': True
            })

            # 스탑/익절 상태 초기화
            self._current_stop_loss = None
            self._current_take_profit = None
            self._current_entry_price = None

            return True

        return False

    def run(self) -> BacktestResult:
        """
        백테스트 실행

        execute_on_next_open=True (기본값, 권장):
            - t시점 종가로 신호 생성 → t+1시점 시가로 체결
            - Look-Ahead Bias 방지 (현실적인 백테스팅)
            - 실제 트레이딩과 동일한 조건

        execute_on_next_open=False:
            - t시점 종가로 신호 생성 → t시점 종가로 체결
            - Look-Ahead Bias 존재 (과대평가 위험)
            - 빠른 테스트용으로만 사용
        """
        # [최적화] 지표 사전 계산 - O(N²) → O(N)
        # 전략이 prepare_indicators를 구현했다면 백테스트 시작 전 한 번만 호출
        if hasattr(self.strategy, 'prepare_indicators'):
            print("[최적화] 지표 사전 계산 중...", end=" ", flush=True)
            self.strategy.prepare_indicators(self.data)
            print("완료")

        total_bars = len(self.data)
        pending_signal = None  # 다음 봉에서 실행할 대기 신호

        for i in range(total_bars):
            # 진행 상황 출력 (10% 단위)
            if i % max(1, total_bars // 10) == 0 or i == total_bars - 1:
                progress = (i + 1) / total_bars * 100
                print(f"\r[백테스팅 진행] {i+1}/{total_bars} ({progress:.1f}%)", end="", flush=True)

            # 1. 현재 시점 데이터 추출
            current_bar = self.data.iloc[:i+1]
            current_bar_data = current_bar.iloc[-1]

            # 1.5. 봉 내 스탑/익절 체크 (use_intrabar_stops 모드)
            if self.use_intrabar_stops:
                exited = self._check_intrabar_exit(current_bar_data)
                if exited:
                    # 스탑/익절로 청산되면 대기 신호 취소
                    pending_signal = None

            # 2. 대기 중인 신호가 있으면 현재 봉 시가로 체결 (execute_on_next_open 모드)
            if self.execute_on_next_open and pending_signal is not None:
                try:
                    # 시가로 체결 (Look-Ahead Bias 방지)
                    self._execute_order(pending_signal, current_bar_data, use_open_price=True)
                except Exception as e:
                    print(f"\n⚠️  시점 {i+1}에서 대기 주문 실행 오류: {str(e)}")
                pending_signal = None  # 처리 완료

            # 3. 전략 시그널 생성 (portfolio 전달 - 매도 신호 생성을 위해)
            try:
                signal = self.strategy.generate_signal(current_bar, portfolio=self.portfolio)
            except Exception as e:
                # 에러 발생 시 로깅하고 계속 진행
                print(f"\n⚠️  시점 {i+1}에서 신호 생성 오류: {str(e)}")
                signal = None

            # 4. 주문 처리
            if signal:
                if self.execute_on_next_open:
                    # 다음 봉 시가에 체결하기 위해 신호 저장
                    # 마지막 봉이면 체결 불가 (다음 봉이 없음)
                    if i < total_bars - 1:
                        pending_signal = signal
                    # else: 마지막 봉의 신호는 무시 (체결할 다음 봉이 없음)
                else:
                    # 즉시 종가로 체결 (기존 방식, Look-Ahead Bias 있음)
                    try:
                        self._execute_order(signal, current_bar_data, use_open_price=False)
                    except Exception as e:
                        print(f"\n⚠️  시점 {i+1}에서 주문 실행 오류: {str(e)}")

            # 5. 포트폴리오 업데이트
            self.portfolio.update(current_bar_data)
            self.equity_curve.append(self.portfolio.total_value)

        print()  # 진행 상황 출력 후 줄바꿈

        # 6. 결과 분석
        return self._analyze_results()
    
    def _execute_order(self, signal, current_bar: pd.Series, use_open_price: bool = False):
        """
        주문 실행 (슬리피지 및 분할 주문 적용)

        Args:
            signal: 거래 신호
            current_bar: 현재 봉 데이터
            use_open_price: True면 시가로 체결, False면 종가로 체결
        """
        # 체결 가격 결정: 시가 또는 종가
        if use_open_price:
            current_price = current_bar['open']  # 다음 봉 시가로 체결 (Look-Ahead Bias 방지)
        else:
            current_price = current_bar['close']  # 현재 봉 종가로 체결 (기존 방식)
        
        if signal.action == 'buy':
            # 매수 신호
            if signal.size is None:
                # 포지션 크기 계산
                signal.size = self.strategy.calculate_position_size(signal, self.portfolio)
            
            # 슬리피지 계산
            slippage_info = self._calculate_order_slippage(
                order_type='buy',
                expected_price=current_price,
                order_size=signal.size,
                current_bar=current_bar
            )
            
            actual_price = slippage_info['actual_avg_price']
            
            # 분할 주문 처리
            if self.use_split_orders:
                execution_result = self._execute_split_order(
                    signal=signal,
                    current_bar=current_bar,
                    slippage_info=slippage_info
                )
                if execution_result:
                    return
            
            # 일반 주문 실행
            try:
                position = self.portfolio.open_position(
                    symbol=self.ticker,
                    size=signal.size,
                    price=actual_price,  # 슬리피지 적용된 가격
                    commission=self.commission,
                    slippage=0  # 이미 계산됨
                )
                self.orders.append({
                    'action': 'buy',
                    'price': current_price,
                    'actual_price': actual_price,
                    'size': signal.size,
                    'timestamp': current_bar.name,
                    'slippage_info': slippage_info
                })

                # 스탑/익절 가격 추적 (use_intrabar_stops 모드용)
                self._current_entry_price = actual_price
                self._current_stop_loss = getattr(signal, 'stop_loss', None)
                self._current_take_profit = getattr(signal, 'take_profit', None)

                # 슬리피지 통계 기록
                self._record_slippage(slippage_info, current_bar.name)
            except Exception as e:
                # 자금 부족 등
                pass
        
        elif signal.action == 'sell' or signal.action == 'close':
            # 매도 신호
            # 슬리피지 계산
            position = self.portfolio.positions.get(self.ticker)
            if position and position.size > 0:
                slippage_info = self._calculate_order_slippage(
                    order_type='sell',
                    expected_price=current_price,
                    order_size=position.size,
                    current_bar=current_bar
                )
                actual_price = slippage_info['actual_avg_price']
            else:
                slippage_info = None
                actual_price = current_price
            
            trade = self.portfolio.close_position(
                symbol=self.ticker,
                price=actual_price,  # 슬리피지 적용된 가격
                commission=self.commission,
                slippage=0  # 이미 계산됨
            )
            if trade:
                self.trades.append(trade)
                self.orders.append({
                    'action': 'sell',
                    'price': current_price,
                    'actual_price': actual_price,
                    'size': trade.size,
                    'timestamp': current_bar.name,
                    'slippage_info': slippage_info
                })

                # 스탑/익절 상태 초기화
                self._current_stop_loss = None
                self._current_take_profit = None
                self._current_entry_price = None

                # 슬리피지 통계 기록
                if slippage_info:
                    self._record_slippage(slippage_info, current_bar.name)
    
    def _calculate_order_slippage(
        self,
        order_type: str,
        expected_price: float,
        order_size: float,
        current_bar: pd.Series
    ) -> dict:
        """주문 슬리피지 계산"""
        if self.slippage_model['type'] == 'orderbook':
            # 오더북 기반 슬리피지 계산
            orderbook_provider = self.slippage_model.get('orderbook_provider')
            
            if orderbook_provider and callable(orderbook_provider):
                orderbook = orderbook_provider()
                if orderbook:
                    return self.strategy.calculate_slippage(
                        order_type=order_type,
                        expected_price=expected_price,
                        order_size=order_size,
                        orderbook=orderbook
                    )
            
            # 오더북 없으면 기본 슬리피지 사용
            default_slippage = self.slippage_model.get('default_slippage', 0.001)
            if order_type == 'buy':
                actual_price = expected_price * (1 + default_slippage)
            else:
                actual_price = expected_price * (1 - default_slippage)
            
            return {
                'actual_avg_price': actual_price,
                'slippage_amount': abs(actual_price - expected_price) * order_size,
                'slippage_pct': default_slippage
            }
        else:
            # 퍼센트 기반 슬리피지
            slippage_pct = self.slippage_model.get(
                'buy_slippage' if order_type == 'buy' else 'sell_slippage',
                self.slippage
            )
            
            if order_type == 'buy':
                actual_price = expected_price * (1 + slippage_pct)
            else:
                actual_price = expected_price * (1 - slippage_pct)
            
            return {
                'actual_avg_price': actual_price,
                'slippage_amount': abs(actual_price - expected_price) * order_size,
                'slippage_pct': slippage_pct
            }
    
    def _execute_split_order(self, signal, current_bar: pd.Series, slippage_info: dict):
        """분할 주문 실행"""
        # 오더북 가져오기
        orderbook_provider = self.slippage_model.get('orderbook_provider')
        if not orderbook_provider or not callable(orderbook_provider):
            return None
        
        orderbook = orderbook_provider()
        if not orderbook:
            return None
        
        # 최적 분할 개수 계산
        num_splits = self.strategy.calculate_optimal_splits(
            order_size=signal.size,
            orderbook=orderbook,
            order_type='buy'
        )
        
        if num_splits <= 1:
            return None  # 분할 불필요
        
        # 분할 주문 시뮬레이션
        execution_result = self.strategy.simulate_split_order_execution(
            total_size=signal.size,
            num_splits=num_splits,
            orderbook=orderbook,
            order_type='buy'
        )
        
        # 포트폴리오에 포지션 추가
        avg_price = execution_result['avg_execution_price']
        
        try:
            position = self.portfolio.open_position(
                symbol=self.ticker,
                size=signal.size,
                price=avg_price,
                commission=self.commission,
                slippage=0  # 이미 계산됨
            )
            
            self.orders.append({
                'action': 'buy',
                'price': current_bar['close'],
                'actual_price': avg_price,
                'size': signal.size,
                'timestamp': current_bar.name,
                'split_orders': execution_result['filled_orders'],
                'total_slippage': execution_result['total_slippage']
            })
            
            # 슬리피지 통계 기록
            self._record_slippage({
                'actual_avg_price': avg_price,
                'slippage_amount': abs(avg_price - current_bar['close']) * signal.size,
                'slippage_pct': execution_result['total_slippage']
            }, current_bar.name)
            
            return execution_result
        except Exception as e:
            return None
    
    def _record_slippage(self, slippage_info: dict, timestamp):
        """슬리피지 통계 기록"""
        self.slippage_statistics.append({
            'timestamp': timestamp,
            'slippage_pct': slippage_info.get('slippage_pct', 0),
            'slippage_amount': slippage_info.get('slippage_amount', 0),
            'actual_price': slippage_info.get('actual_avg_price', 0)
        })
    
    def _analyze_results(self) -> BacktestResult:
        """결과 분석"""
        from .performance import PerformanceAnalyzer

        metrics = PerformanceAnalyzer.calculate_metrics(
            equity_curve=self.equity_curve,
            trades=self.portfolio.closed_trades,
            initial_capital=self.initial_capital,
            data_interval=self.data_interval  # 데이터 간격 전달 (연율화 계산용)
        )
        
        # 슬리피지 통계 추가
        if self.slippage_statistics:
            total_slippage_amount = sum(s['slippage_amount'] for s in self.slippage_statistics)
            avg_slippage_pct = sum(s['slippage_pct'] for s in self.slippage_statistics) / len(self.slippage_statistics)
            
            metrics['slippage_stats'] = {
                'total_slippage_amount': total_slippage_amount,
                'avg_slippage_pct': avg_slippage_pct,
                'num_orders': len(self.slippage_statistics)
            }
        
        return BacktestResult(
            initial_capital=self.initial_capital,
            final_equity=self.equity_curve[-1] if self.equity_curve else self.initial_capital,
            equity_curve=self.equity_curve,
            trades=self.portfolio.closed_trades,
            metrics=metrics,
            execution_mode='next_open' if self.execute_on_next_open else 'close'
        )

