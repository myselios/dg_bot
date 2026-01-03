"""
AI 기반 거래 전략

Clean Architecture (2026-01-03):
- Container/AIPort를 통한 AI 분석
- AIService 삭제됨
"""
from typing import Optional, TYPE_CHECKING
import pandas as pd
from decimal import Decimal
from .strategy import Strategy, Signal
from .portfolio import Portfolio
from .rule_based_strategy import RuleBasedBreakoutStrategy
from ..trading.indicators import TechnicalIndicators

if TYPE_CHECKING:
    from ..container import Container
    from ..application.ports.outbound.ai_port import AIPort


class AITradingStrategy(Strategy):
    """AI 기반 거래 전략"""

    def __init__(
        self,
        ticker: str,
        risk_per_trade: float = 0.02,
        max_position_size: float = 0.3,
        container: 'Container' = None,
        ai_port: 'AIPort' = None,
    ):
        self.ticker = ticker
        self.risk_per_trade = risk_per_trade
        self.max_position_size = max_position_size
        self._container = container
        self._ai_port = ai_port

    def generate_signal(self, data: pd.DataFrame, portfolio: Optional[Portfolio] = None) -> Optional[Signal]:
        """AI 분석 기반 신호 생성"""
        if len(data) == 0:
            return None

        # 1단계: 룰 기반 필터링
        rule_strategy = RuleBasedBreakoutStrategy(
            ticker=self.ticker,
            risk_per_trade=self.risk_per_trade,
            max_position_size=self.max_position_size
        )
        rule_signal = rule_strategy.generate_signal(data)

        if rule_signal is None:
            return None

        # 2단계: AI 분석
        current_price = data['close'].iloc[-1]
        current_date = data.index[-1] if hasattr(data.index[-1], 'strftime') else str(data.index[-1])

        if not hasattr(AITradingStrategy, '_ai_call_count'):
            AITradingStrategy._ai_call_count = 0
        AITradingStrategy._ai_call_count += 1

        if AITradingStrategy._ai_call_count <= 5 or AITradingStrategy._ai_call_count % 10 == 0:
            print(f"\n[AI 분석 {AITradingStrategy._ai_call_count}회] {current_date} - 룰 통과, AI 검증 중...")

        try:
            technical_indicators = TechnicalIndicators.get_latest_indicators(data)
            ai_decision = self._analyze_with_ai(current_price, technical_indicators, rule_signal)

            if not ai_decision:
                return None
        except Exception as e:
            print(f"\n⚠️  AI 분석 오류 (시점 {current_date}): {str(e)}")
            return None

        # 신호 변환
        if ai_decision['decision'] == 'buy':
            atr = technical_indicators.get('atr', current_price * 0.02)
            stop_loss = current_price - (2 * atr)
            take_profit = current_price + (3 * atr)

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

    def _analyze_with_ai(
        self,
        current_price: float,
        technical_indicators: dict,
        rule_signal: Signal,
    ) -> Optional[dict]:
        """AIPort를 통한 AI 분석"""
        import asyncio
        from ..application.dto.analysis import AnalysisRequest, TechnicalIndicators as TechIndicatorsDTO

        ai_port = self._get_ai_port()
        if ai_port is None:
            raise RuntimeError("Container 또는 ai_port가 필요합니다")

        # AnalysisRequest 생성
        request = AnalysisRequest(
            ticker=self.ticker,
            current_price=Decimal(str(current_price)),
            indicators=TechIndicatorsDTO(
                rsi=Decimal(str(technical_indicators.get('rsi', 50))),
                macd=Decimal(str(technical_indicators.get('macd', 0))),
                macd_signal=Decimal(str(technical_indicators.get('macd_signal', 0))),
                bb_upper=Decimal(str(technical_indicators.get('bb_upper', current_price * 1.02))),
                bb_lower=Decimal(str(technical_indicators.get('bb_lower', current_price * 0.98))),
                bb_middle=Decimal(str(technical_indicators.get('bb_middle', current_price))),
                atr=Decimal(str(technical_indicators.get('atr', current_price * 0.02))),
            ),
            position_info={
                'rule_breakout': {
                    'passed': True,
                    'gate1': rule_signal.reason.get('gate1', ''),
                    'gate2': rule_signal.reason.get('gate2', ''),
                    'gate3': rule_signal.reason.get('gate3', ''),
                    'strategy': 'volatility_breakout'
                }
            },
        )

        # async 호출
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, ai_port.analyze(request))
                    decision = future.result(timeout=60)
            else:
                decision = loop.run_until_complete(ai_port.analyze(request))
        except RuntimeError:
            decision = asyncio.run(ai_port.analyze(request))

        # 결과 변환
        decision_map = {'BUY': 'buy', 'SELL': 'sell', 'HOLD': 'hold'}
        return {
            'decision': decision_map.get(decision.decision.name, 'hold'),
            'confidence': str(decision.confidence),
            'reason': decision.reasoning,
        }

    def _get_ai_port(self):
        """AIPort 획득"""
        if self._ai_port is not None:
            return self._ai_port
        if self._container is not None:
            return self._container.get_ai_port()
        return None

    def calculate_position_size(self, signal: Signal, portfolio: Portfolio) -> float:
        """포지션 크기 계산"""
        if signal.stop_loss:
            risk_amount = portfolio.equity * self.risk_per_trade
            price_risk = signal.price - signal.stop_loss

            if price_risk > 0:
                position_size = risk_amount / price_risk
                max_size = (portfolio.equity * self.max_position_size) / signal.price
                return min(position_size, max_size)

        return (portfolio.equity * 0.1) / signal.price
