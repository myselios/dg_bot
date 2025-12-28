"""
AI 기반 거래 전략
"""
from typing import Optional
import pandas as pd
from .strategy import Strategy, Signal
from .portfolio import Portfolio
from .rule_based_strategy import RuleBasedBreakoutStrategy
from ..ai.service import AIService
from ..trading.indicators import TechnicalIndicators


class AITradingStrategy(Strategy):
    """AI 기반 거래 전략"""
    
    def __init__(
        self,
        ai_service: AIService,
        ticker: str,
        risk_per_trade: float = 0.02,  # 거래당 리스크 2%
        max_position_size: float = 0.3  # 최대 포지션 30%
    ):
        self.ai_service = ai_service
        self.ticker = ticker
        self.risk_per_trade = risk_per_trade
        self.max_position_size = max_position_size
        
    def generate_signal(self, data: pd.DataFrame, portfolio: Optional[Portfolio] = None) -> Optional[Signal]:
        """
        AI 분석 기반 신호 생성
        룰 기반 필터를 먼저 통과한 경우에만 AI 호출
        
        Args:
            data: 현재 시점까지의 차트 데이터
            portfolio: 포트폴리오 객체 (선택적, 백테스팅에서 전달됨)
        """
        
        if len(data) == 0:
            return None
        
        # ============================================
        # 1단계: 룰 기반 필터링 (AI 호출 전 사전 체크)
        # ============================================
        rule_strategy = RuleBasedBreakoutStrategy(
            ticker=self.ticker,
            risk_per_trade=self.risk_per_trade,
            max_position_size=self.max_position_size
        )
        
        # 룰 기반 신호 생성 (AI 호출 없음)
        rule_signal = rule_strategy.generate_signal(data)
        
        if rule_signal is None:
            # 룰을 통과하지 못했으면 AI 호출 없이 None 반환
            return None
        
        # 룰을 통과했으므로 AI로 최종 검증
        # ============================================
        # 2단계: AI 분석 (룰 통과 시점만)
        # ============================================
        current_price = data['close'].iloc[-1]
        current_date = data.index[-1] if hasattr(data.index[-1], 'strftime') else str(data.index[-1])
        
        # AI 호출 횟수 추적 (클래스 변수로 관리)
        if not hasattr(AITradingStrategy, '_ai_call_count'):
            AITradingStrategy._ai_call_count = 0
        AITradingStrategy._ai_call_count += 1
        
        # AI 호출 시점 출력 (백테스팅 중임을 명시)
        if AITradingStrategy._ai_call_count <= 5 or AITradingStrategy._ai_call_count % 10 == 0:
            print(f"\n[AI 분석 {AITradingStrategy._ai_call_count}회] {current_date} - 룰 통과, AI 검증 중...")
        
        try:
            # 기술적 지표 계산
            technical_indicators = TechnicalIndicators.get_latest_indicators(data)
            
            # AI 분석 데이터 준비 (백테스팅용 - 오더북 없음)
            analysis_data = self.ai_service.prepare_analysis_data(
                chart_data={'day': data},
                orderbook_summary={},  # 백테스트에서는 실제 오더북 없음
                current_status={
                    'current_price': current_price,
                    'krw_balance': 0,
                    'coin_balance': 0
                },
                technical_indicators=technical_indicators
            )
            
            # 룰 통과 정보 추가 (AI에게 컨텍스트 제공)
            analysis_data['rule_breakout'] = {
                'passed': True,
                'gate1': rule_signal.reason.get('gate1', ''),
                'gate2': rule_signal.reason.get('gate2', ''),
                'gate3': rule_signal.reason.get('gate3', ''),
                'strategy': 'volatility_breakout'
            }
            
            # AI 분석 수행
            ai_decision = self.ai_service.analyze(self.ticker, analysis_data)
            
            if not ai_decision:
                return None
        except Exception as e:
            # AI 분석 중 에러 발생 시 로깅하고 None 반환
            print(f"\n⚠️  AI 분석 오류 (시점 {current_date}): {str(e)}")
            return None
        
        # 신호 변환
        if ai_decision['decision'] == 'buy':
            # 스탑로스 계산 (ATR 기반)
            atr = technical_indicators.get('atr', current_price * 0.02)
            stop_loss = current_price - (2 * atr)
            take_profit = current_price + (3 * atr)  # 1:1.5 리스크 보상비
            
            return Signal(
                action='buy',
                price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reason=ai_decision
            )
        
        elif ai_decision['decision'] == 'sell':
            return Signal(
                action='sell',
                price=current_price,
                reason=ai_decision
            )
        
        return None
    
    def calculate_position_size(
        self, 
        signal: Signal, 
        portfolio: Portfolio
    ) -> float:
        """포지션 크기 계산 (리스크 기반)"""
        
        if signal.stop_loss:
            # ATR 기반 포지션 사이징
            risk_amount = portfolio.equity * self.risk_per_trade
            price_risk = signal.price - signal.stop_loss
            
            if price_risk > 0:
                position_size = risk_amount / price_risk
                
                # 최대 포지션 제한
                max_size = (portfolio.equity * self.max_position_size) / signal.price
                position_size = min(position_size, max_size)
                
                return position_size
        
        # 기본: 포트폴리오의 10%
        return (portfolio.equity * 0.1) / signal.price

