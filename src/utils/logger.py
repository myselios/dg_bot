"""
로깅 및 출력 관리
"""
from datetime import datetime
from typing import Optional
import pandas as pd


class Logger:
    """출력 및 로깅 관리 클래스"""
    
    SEPARATOR_LENGTH = 60
    
    @staticmethod
    def _separator() -> str:
        """구분선"""
        return "=" * Logger.SEPARATOR_LENGTH
    
    @staticmethod
    def print_header(title: str):
        """헤더 출력"""
        print(f"\n{Logger._separator()}")
        print(title)
        print(Logger._separator())
    
    @staticmethod
    def print_investment_status(balances: list, upbit_client, target_currency: str = None):
        """
        투자 상태 출력
        
        Args:
            balances: 잔고 리스트
            upbit_client: Upbit 클라이언트
            target_currency: 표시할 대상 통화 (None이면 모든 통화 표시)
        """
        Logger.print_header("📊 현재 투자 상태")
        
        total_krw_value = 0
        
        for balance in balances:
            currency = balance['currency']
            amount = float(balance['balance'])
            locked = float(balance['locked'])
            avg_buy_price = float(balance['avg_buy_price'])
            
            # target_currency가 지정된 경우 필터링
            if target_currency and currency != 'KRW' and currency != target_currency:
                continue
            
            if currency == 'KRW':
                print(f"\n💵 원화 (KRW)")
                print(f"   사용가능: {amount:,.0f}원")
                print(f"   주문중: {locked:,.0f}원")
                total_krw_value += amount + locked
            else:
                ticker = f"KRW-{currency}"
                # upbit_client를 통해 가격 조회 (에러 처리 포함)
                try:
                    current_price = upbit_client.get_current_price(ticker)
                except Exception:
                    current_price = None
                
                if current_price:
                    current_value = (amount + locked) * current_price
                    profit_loss = current_value - (amount + locked) * avg_buy_price
                    profit_loss_rate = (
                        (profit_loss / ((amount + locked) * avg_buy_price) * 100)
                        if avg_buy_price > 0
                        else 0
                    )
                    
                    print(f"\n🪙 {currency}")
                    print(f"   보유량: {amount:.8f} (주문중: {locked:.8f})")
                    print(f"   평균 매수가: {avg_buy_price:,.0f}원")
                    print(f"   현재가: {current_price:,.0f}원")
                    print(f"   평가금액: {current_value:,.0f}원")
                    print(f"   손익: {profit_loss:,.0f}원 ({profit_loss_rate:+.2f}%)")
                    
                    total_krw_value += current_value
                else:
                    # 가격 조회 실패 시 기본 정보만 출력
                    print(f"\n🪙 {currency}")
                    print(f"   보유량: {amount:.8f} (주문중: {locked:.8f})")
                    print(f"   평균 매수가: {avg_buy_price:,.0f}원")
                    print(f"   현재가: 조회 실패")
        
        print(f"\n{Logger._separator()}")
        print(f"💰 총 평가금액: {total_krw_value:,.0f}원")
        print(f"{Logger._separator()}\n")
    
    @staticmethod
    def print_orderbook(ticker: str, orderbook: Optional[list]):
        """오더북 출력"""
        Logger.print_header(f"📖 오더북 정보 - {ticker}")
        
        if not orderbook:
            return
        
        orderbook_units = orderbook[0]['orderbook_units']
        
        print("\n[매도 호가 (Ask)]")
        print(f"{'가격':>15} | {'수량':>15} | {'누적':>15}")
        print("-" * Logger.SEPARATOR_LENGTH)
        
        for unit in reversed(orderbook_units[:5]):
            ask_price = unit['ask_price']
            ask_size = unit['ask_size']
            print(f"{ask_price:>15,.0f} | {ask_size:>15,.4f} | {ask_price * ask_size:>15,.0f}")
        
        print("\n" + Logger._separator())
        
        print("\n[매수 호가 (Bid)]")
        print(f"{'가격':>15} | {'수량':>15} | {'누적':>15}")
        print("-" * Logger.SEPARATOR_LENGTH)
        
        for unit in orderbook_units[:5]:
            bid_price = unit['bid_price']
            bid_size = unit['bid_size']
            print(f"{bid_price:>15,.0f} | {bid_size:>15,.4f} | {bid_price * bid_size:>15,.0f}")
        
        print(f"\n{Logger._separator()}\n")
    
    @staticmethod
    def print_chart_stats(ticker: str, df_day: pd.DataFrame):
        """차트 통계 출력"""
        Logger.print_header(f"📈 차트 데이터 - {ticker}")
        
        print("\n[일봉 최근 5일]")
        print(df_day.tail(5).to_string())
        
        print("\n\n[일봉 통계 (30일)]")
        print(f"최고가: {df_day['high'].max():,.0f}원")
        print(f"최저가: {df_day['low'].min():,.0f}원")
        print(f"평균가: {df_day['close'].mean():,.0f}원")
        print(f"현재가: {df_day['close'].iloc[-1]:,.0f}원")
        print(f"거래량 평균: {df_day['volume'].mean():.2f}")
        
        price_change = (
            (df_day['close'].iloc[-1] - df_day['close'].iloc[0])
            / df_day['close'].iloc[0]
            * 100
        )
        print(f"30일 변동률: {price_change:+.2f}%")
        print(f"\n{Logger._separator()}\n")
    
    @staticmethod
    def print_ai_response(timestamp: str, ai_response: str):
        """AI 응답 출력"""
        print(f"\n[{timestamp}] AI 응답:")
        print(ai_response)
    
    @staticmethod
    def print_decision(decision: str, confidence: str, reason: str):
        """AI 판단 결과 출력"""
        # decision 한글 변환
        decision_kr = {
            "buy": "매수",
            "sell": "매도",
            "hold": "보유",
            "strong_buy": "강력 매수",
            "strong_sell": "강력 매도"
        }.get(decision.lower(), decision.upper())
        
        # confidence 한글 변환
        confidence_kr = {
            "high": "높음",
            "medium": "보통",
            "low": "낮음",
            "very_low": "매우 낮음"
        }.get(confidence.lower(), confidence.upper())
        
        print(f"\n{Logger._separator()}")
        print(f"🎯 AI 판단: {decision_kr}")
        print(f"📊 신뢰도: {confidence_kr}")
        print(f"💡 이유: {reason}")
        print(f"{Logger._separator()}\n")
    
    @staticmethod
    def print_error(message: str):
        """에러 메시지 출력"""
        print(f"❌ {message}")
    
    @staticmethod
    def print_success(message: str):
        """성공 메시지 출력"""
        print(f"✅ {message}")
    
    @staticmethod
    def print_info(message: str):
        """정보 메시지 출력"""
        print(f"ℹ️  {message}")
    
    @staticmethod
    def print_warning(message: str):
        """경고 메시지 출력"""
        print(f"⚠️  {message}")
    
    @staticmethod
    def print_program_start(ticker: str):
        """프로그램 시작 출력"""
        print(f"\n🤖 AI 자동매매 프로그램 시작")
        print(Logger._separator())
        print(f"시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"대상: {ticker}")
        print(Logger._separator())

