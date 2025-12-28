"""
백테스팅 엔진
"""
from typing import List
from dataclasses import dataclass
import pandas as pd
from .strategy import Strategy
from .portfolio import Portfolio


@dataclass
class BacktestResult:
    """백테스트 결과"""
    initial_capital: float
    final_equity: float
    equity_curve: List[float]
    trades: List
    metrics: dict


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
        use_split_orders: bool = False  # 분할 주문 사용 여부
    ):
        self.strategy = strategy
        self.data = data
        self.ticker = ticker
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.use_split_orders = use_split_orders
        
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
        
    def run(self) -> BacktestResult:
        """백테스트 실행"""
        total_bars = len(self.data)
        
        for i in range(total_bars):
            # 진행 상황 출력 (10% 단위)
            if i % max(1, total_bars // 10) == 0 or i == total_bars - 1:
                progress = (i + 1) / total_bars * 100
                print(f"\r[백테스팅 진행] {i+1}/{total_bars} ({progress:.1f}%)", end="", flush=True)
            
            # 1. 현재 시점 데이터 추출
            current_bar = self.data.iloc[:i+1]
            
            # 2. 전략 시그널 생성 (portfolio 전달 - 매도 신호 생성을 위해)
            try:
                signal = self.strategy.generate_signal(current_bar, portfolio=self.portfolio)
            except Exception as e:
                # 에러 발생 시 로깅하고 계속 진행
                print(f"\n⚠️  시점 {i+1}에서 신호 생성 오류: {str(e)}")
                signal = None
            
            # 3. 주문 실행
            if signal:
                try:
                    self._execute_order(signal, current_bar.iloc[-1])
                except Exception as e:
                    print(f"\n⚠️  시점 {i+1}에서 주문 실행 오류: {str(e)}")
            
            # 4. 포트폴리오 업데이트
            self.portfolio.update(current_bar.iloc[-1])
            self.equity_curve.append(self.portfolio.total_value)
        
        print()  # 진행 상황 출력 후 줄바꿈
        
        # 5. 결과 분석
        return self._analyze_results()
    
    def _execute_order(self, signal, current_bar: pd.Series):
        """주문 실행 (슬리피지 및 분할 주문 적용)"""
        current_price = current_bar['close']
        
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
            initial_capital=self.initial_capital
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
            metrics=metrics
        )

