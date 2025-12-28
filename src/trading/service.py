"""
거래 서비스
"""
import time
from typing import Optional
from ..config.settings import TradingConfig
from ..api.interfaces import IExchangeClient
from ..utils.logger import Logger
from ..exceptions import InsufficientFundsError, OrderExecutionError
from ..data.collector import DataCollector
from ..backtesting.strategy import Strategy


class TradingService:
    """거래 로직 처리 클래스"""
    
    def __init__(
        self,
        exchange_client: IExchangeClient,
        data_collector: Optional[DataCollector] = None,
        strategy: Optional[Strategy] = None
    ):
        """
        거래 서비스 초기화
        
        Args:
            exchange_client: 거래소 클라이언트 인터페이스 (의존성 역전 원칙 적용)
            data_collector: 데이터 수집기 (슬리피지 계산용, 선택사항)
            strategy: 거래 전략 (슬리피지 계산용, 선택사항)
        """
        self.exchange = exchange_client
        self.config = TradingConfig
        self.data_collector = data_collector
        self.strategy = strategy
    
    def calculate_fee(self, order_amount: float) -> float:
        """
        주문 금액에 대한 수수료 계산
        
        Args:
            order_amount: 주문 금액
            
        Returns:
            수수료 금액
        """
        fee_by_rate = order_amount * self.config.FEE_RATE
        return max(fee_by_rate, self.config.MIN_FEE)
    
    def calculate_available_buy_amount(self, balance: float) -> float:
        """
        보유 현금에서 수수료를 고려한 실제 매수 가능 금액 계산
        
        Args:
            balance: 보유 현금
            
        Returns:
            매수 가능 금액 (매수 불가능하면 0)
        """
        min_required = self.config.MIN_ORDER_AMOUNT + self.config.MIN_FEE
        
        if balance < min_required:
            return 0
        
        target_amount = balance * self.config.BUY_PERCENTAGE
        fee = self.calculate_fee(target_amount)
        net_amount = target_amount - fee
        
        if net_amount >= self.config.MIN_ORDER_AMOUNT:
            available = min(target_amount, balance)
        else:
            if target_amount * self.config.FEE_RATE < self.config.MIN_FEE:
                available = self.config.MIN_ORDER_AMOUNT + self.config.MIN_FEE
            else:
                available = self.config.MIN_ORDER_AMOUNT / (1 - self.config.FEE_RATE)
            
            available = min(available, balance)
            fee = self.calculate_fee(available)
            net_amount = available - fee
            
            if net_amount < self.config.MIN_ORDER_AMOUNT:
                if balance >= min_required:
                    available = min_required
                else:
                    return 0
        
        return available
    
    def execute_buy(self, ticker: str) -> dict:
        """
        매수 실행
        
        Args:
            ticker: 거래 종목
            
        Returns:
            거래 정보 딕셔너리:
            {
                'success': bool,
                'trade_id': str (optional),
                'price': float (optional),
                'amount': float (optional),
                'total': float (optional),
                'fee': float (optional),
                'error': str (optional)
            }
        """
        krw_balance = self.exchange.get_balance("KRW")
        buy_amount = self.calculate_available_buy_amount(krw_balance)
        
        if buy_amount == 0:
            min_required = self.config.MIN_ORDER_AMOUNT + self.config.MIN_FEE
            error_msg = (
                f"매수 실패: 최소 주문 금액({self.config.MIN_ORDER_AMOUNT:,}원) + "
                f"최소 수수료({self.config.MIN_FEE:,}원) = {min_required:,}원보다 "
                f"잔고가 부족합니다."
            )
            Logger.print_error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
        
        fee = self.calculate_fee(buy_amount)
        net_amount = buy_amount - fee
        
        Logger.print_info(
            f"💰 매수 시도: {buy_amount:,.0f}원 "
            f"(수수료: {fee:,.0f}원, 실제 매수 금액: {net_amount:,.0f}원)"
        )
        
        try:
            result = self.exchange.buy_market_order(ticker, buy_amount)
            if result:
                Logger.print_success("매수 주문 성공!")
                Logger.print_info(f"주문 UUID: {result.get('uuid', 'N/A')}")
                
                # Upbit 주문 결과에서 거래 정보 추출
                trade_price = result.get('trades', [{}])[0].get('price', 0) if result.get('trades') else result.get('price', 0)
                trade_volume = result.get('executed_volume', result.get('volume', 0))
                
                return {
                    'success': True,
                    'trade_id': result.get('uuid'),
                    'price': float(trade_price) if trade_price else 0,
                    'amount': float(trade_volume) if trade_volume else 0,
                    'total': float(buy_amount),
                    'fee': float(result.get('paid_fee', fee))
                }
            else:
                error_msg = "매수 주문 실패: 주문 결과가 없습니다."
                Logger.print_error(error_msg)
                return {
                    'success': False,
                    'error': error_msg
                }
        except Exception as e:
            error_msg = f"매수 주문 실패: {str(e)}"
            Logger.print_error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def execute_sell(self, ticker: str) -> dict:
        """
        매도 실행
        
        Args:
            ticker: 거래 종목
            
        Returns:
            거래 정보 딕셔너리:
            {
                'success': bool,
                'trade_id': str (optional),
                'price': float (optional),
                'amount': float (optional),
                'total': float (optional),
                'fee': float (optional),
                'error': str (optional)
            }
        """
        coin_balance = self.exchange.get_balance(ticker)
        
        if coin_balance <= 0:
            # 보유량이 없으면 매도를 시도하지 않고 조용히 반환
            info_msg = f"보유한 {ticker}가 없어 매도를 수행하지 않습니다."
            Logger.print_info(info_msg)
            return {
                'success': False,
                'error': info_msg
            }
        
        sell_volume = coin_balance * self.config.SELL_PERCENTAGE
        Logger.print_info(f"💸 매도 시도: {sell_volume:.8f} {ticker}")
        
        try:
            result = self.exchange.sell_market_order(ticker, sell_volume)
            if result:
                Logger.print_success("매도 주문 성공!")
                Logger.print_info(f"주문 UUID: {result.get('uuid', 'N/A')}")
                
                # Upbit 주문 결과에서 거래 정보 추출
                trade_price = result.get('trades', [{}])[0].get('price', 0) if result.get('trades') else result.get('price', 0)
                trade_volume = result.get('executed_volume', result.get('volume', 0))
                total_krw = float(trade_price) * float(trade_volume) if trade_price and trade_volume else 0
                
                return {
                    'success': True,
                    'trade_id': result.get('uuid'),
                    'price': float(trade_price) if trade_price else 0,
                    'amount': float(trade_volume) if trade_volume else 0,
                    'total': total_krw,
                    'fee': float(result.get('paid_fee', 0))
                }
            else:
                error_msg = "매도 주문 실패: 주문 결과가 없습니다."
                Logger.print_error(error_msg)
                return {
                    'success': False,
                    'error': error_msg
                }
        except Exception as e:
            error_msg = f"매도 주문 실패: {str(e)}"
            Logger.print_error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def execute_hold(self):
        """보유 유지"""
        Logger.print_info("⏸️  보유 유지: 현재 포지션을 유지합니다.")
    
    def execute_buy_with_slippage(
        self,
        ticker: str,
        amount: Optional[float] = None,
        enable_split: bool = False
    ) -> Optional[dict]:
        """
        슬리피지를 고려한 매수 실행
        
        Args:
            ticker: 거래 종목
            amount: 매수 금액 (None이면 가능한 전액)
            enable_split: 분할 주문 사용 여부
            
        Returns:
            실행 결과 딕셔너리 또는 None
        """
        # 금액 계산
        if amount is None:
            krw_balance = self.exchange.get_balance("KRW")
            amount = self.calculate_available_buy_amount(krw_balance)
        
        if amount == 0:
            return {'status': 'insufficient_funds'}
        
        # 슬리피지 계산
        slippage_info = self._calculate_slippage_for_buy(ticker, amount)
        
        # 슬리피지 경고
        if slippage_info.get('warning'):
            Logger.print_warning(slippage_info['warning'])
        
        # 분할 주문 여부 결정
        if enable_split and self.strategy and self.data_collector:
            orderbook = self.data_collector.get_orderbook(ticker)
            if orderbook:
                # ETH 수량으로 변환
                current_price = self.exchange.get_current_price(ticker)
                order_size = amount / current_price
                
                num_splits = self.strategy.calculate_optimal_splits(
                    order_size=order_size,
                    orderbook=orderbook,
                    order_type='buy'
                )
                
                if num_splits > 1:
                    Logger.print_info(f"🔀 분할 매수 실행: {num_splits}개로 분할")
                    return self._execute_split_buy(ticker, amount, num_splits)
        
        # 일반 주문 실행
        Logger.print_info(
            f"💰 매수 실행 (예상 슬리피지: {slippage_info['slippage_pct']*100:.3f}%)"
        )
        
        try:
            order_result = self.exchange.buy_market_order(ticker, amount)
            if order_result:
                Logger.print_success("매수 주문 성공!")
                return {
                    'status': 'success',
                    'slippage_info': slippage_info,
                    'order_result': order_result
                }
            else:
                return {'status': 'failed'}
        except Exception as e:
            Logger.print_error(f"매수 주문 실패: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def execute_sell_with_slippage(self, ticker: str) -> Optional[dict]:
        """
        슬리피지를 고려한 매도 실행
        
        Args:
            ticker: 거래 종목
            
        Returns:
            실행 결과 딕셔너리 또는 None
        """
        coin_balance = self.exchange.get_balance(ticker)
        
        if coin_balance <= 0:
            Logger.print_info(f"보유한 {ticker}가 없어 매도를 수행하지 않습니다.")
            return {'status': 'no_balance'}
        
        # 슬리피지 계산
        slippage_info = self._calculate_slippage_for_sell(ticker, coin_balance)
        
        # 슬리피지 경고
        if slippage_info.get('warning'):
            Logger.print_warning(slippage_info['warning'])
        
        sell_volume = coin_balance * self.config.SELL_PERCENTAGE
        Logger.print_info(
            f"💸 매도 실행: {sell_volume:.8f} {ticker} "
            f"(예상 슬리피지: {slippage_info['slippage_pct']*100:.3f}%)"
        )
        
        try:
            order_result = self.exchange.sell_market_order(ticker, sell_volume)
            if order_result:
                Logger.print_success("매도 주문 성공!")
                return {
                    'status': 'success',
                    'slippage_info': slippage_info,
                    'order_result': order_result
                }
            else:
                return {'status': 'failed'}
        except Exception as e:
            Logger.print_error(f"매도 주문 실패: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def calculate_optimal_buy_amount_with_slippage(
        self,
        ticker: str,
        balance: float,
        expected_slippage_pct: float = 0.005
    ) -> float:
        """
        슬리피지를 고려한 최적 매수 금액 계산
        
        Args:
            ticker: 거래 종목
            balance: 보유 잔액
            expected_slippage_pct: 예상 슬리피지 비율
            
        Returns:
            최적 매수 금액
        """
        # 기본 매수 가능 금액 계산
        base_amount = self.calculate_available_buy_amount(balance)
        
        if base_amount == 0:
            return 0
        
        # 슬리피지를 고려한 조정
        # 슬리피지만큼 추가 비용이 발생하므로 매수 금액을 줄임
        adjusted_amount = base_amount / (1 + expected_slippage_pct)
        
        return min(adjusted_amount, balance)
    
    def _calculate_slippage_for_buy(self, ticker: str, amount: float) -> dict:
        """매수 슬리피지 계산"""
        if not self.strategy or not self.data_collector:
            # 전략이나 데이터 수집기가 없으면 기본 슬리피지 반환
            return {
                'slippage_pct': 0.001,  # 0.1%
                'slippage_amount': amount * 0.001,
                'actual_avg_price': None
            }
        
        try:
            orderbook = self.data_collector.get_orderbook(ticker)
            current_price = self.exchange.get_current_price(ticker)
            
            if not orderbook:
                # 오더북 없으면 기본 슬리피지
                return {
                    'slippage_pct': 0.001,
                    'slippage_amount': amount * 0.001,
                    'actual_avg_price': current_price * 1.001
                }
            
            # ETH 수량으로 변환
            order_size = amount / current_price
            
            # 슬리피지 계산
            slippage_info = self.strategy.calculate_slippage(
                order_type='buy',
                expected_price=current_price,
                order_size=order_size,
                orderbook=orderbook
            )
            
            return slippage_info
        except Exception as e:
            Logger.print_warning(f"슬리피지 계산 실패: {str(e)}, 기본값 사용")
            return {
                'slippage_pct': 0.001,
                'slippage_amount': amount * 0.001,
                'actual_avg_price': None
            }
    
    def _calculate_slippage_for_sell(self, ticker: str, volume: float) -> dict:
        """매도 슬리피지 계산"""
        if not self.strategy or not self.data_collector:
            return {
                'slippage_pct': 0.001,
                'slippage_amount': 0,
                'actual_avg_price': None
            }
        
        try:
            orderbook = self.data_collector.get_orderbook(ticker)
            current_price = self.exchange.get_current_price(ticker)
            
            if not orderbook:
                return {
                    'slippage_pct': 0.001,
                    'slippage_amount': volume * current_price * 0.001,
                    'actual_avg_price': current_price * 0.999
                }
            
            slippage_info = self.strategy.calculate_slippage(
                order_type='sell',
                expected_price=current_price,
                order_size=volume,
                orderbook=orderbook
            )
            
            return slippage_info
        except Exception as e:
            Logger.print_warning(f"슬리피지 계산 실패: {str(e)}, 기본값 사용")
            return {
                'slippage_pct': 0.001,
                'slippage_amount': 0,
                'actual_avg_price': None
            }
    
    def _execute_split_buy(
        self,
        ticker: str,
        total_amount: float,
        num_splits: int
    ) -> dict:
        """분할 매수 실행"""
        split_amounts = [total_amount / num_splits] * num_splits
        filled_orders = []
        
        for i, split_amount in enumerate(split_amounts, 1):
            Logger.print_info(f"  분할 주문 {i}/{num_splits}: {split_amount:,.0f}원")
            
            try:
                order_result = self.exchange.buy_market_order(ticker, split_amount)
                if order_result:
                    filled_orders.append({
                        'order_num': i,
                        'amount': split_amount,
                        'result': order_result
                    })
                    Logger.print_success(f"  분할 주문 {i} 성공")
                else:
                    Logger.print_error(f"  분할 주문 {i} 실패")
            except Exception as e:
                Logger.print_error(f"  분할 주문 {i} 실패: {str(e)}")
            
            # 주문 간 딜레이 (시장 영향 최소화)
            if i < num_splits:
                time.sleep(0.5)
        
        total_filled = sum(order['amount'] for order in filled_orders)
        
        return {
            'status': 'completed' if len(filled_orders) > 0 else 'failed',
            'split_orders': filled_orders,
            'total_filled': total_filled,
            'num_splits': num_splits
        }

