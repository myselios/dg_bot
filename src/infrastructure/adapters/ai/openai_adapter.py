"""
OpenAIAdapter - OpenAI implementation of AIPort.

This adapter wraps OpenAI API calls for AI-based trading analysis.
"""
import json
import os
from decimal import Decimal
from typing import Optional
from datetime import datetime

from src.application.ports.outbound.ai_port import AIPort
from src.application.dto.analysis import (
    AnalysisRequest,
    TradingDecision,
    DecisionType,
)
from src.config.settings import AIConfig


class OpenAIAdapter(AIPort):
    """
    OpenAI adapter implementing AIPort.

    Uses OpenAI API for trading analysis and decision making.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize OpenAI adapter.

        Args:
            api_key: OpenAI API key (uses env OPENAI_API_KEY if not provided)
            model: Model to use (uses AIConfig.MODEL if not provided)
        """
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self._model = model or AIConfig.MODEL
        self._client = None

    @property
    def client(self):
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self._api_key)
            except ImportError:
                raise ImportError("openai package is required for OpenAIAdapter")
        return self._client

    async def analyze(self, request: AnalysisRequest) -> TradingDecision:
        """Analyze market data and return a trading decision."""
        # Validate input type (contract enforcement)
        if not isinstance(request, AnalysisRequest):
            raise TypeError(
                f"analyze() requires AnalysisRequest DTO, got: {type(request)}. "
                f"Use AnalysisRequest(...) instead of dict."
            )

        try:
            # Build analysis prompt
            prompt = self._build_analysis_prompt(request)

            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                temperature=AIConfig.TEMPERATURE,
                max_completion_tokens=AIConfig.MAX_TOKENS,
            )

            # Parse response
            raw_response = response.choices[0].message.content
            return self._parse_decision(raw_response, request.ticker)

        except Exception as e:
            # Return HOLD on error
            return TradingDecision(
                decision=DecisionType.HOLD,
                confidence=Decimal("0"),
                reasoning=f"Analysis failed: {str(e)}",
                raw_response=str(e),
            )

    async def analyze_entry(self, request: AnalysisRequest) -> TradingDecision:
        """Analyze whether to enter a new position."""
        # Add entry-specific context
        request_with_context = AnalysisRequest(
            ticker=request.ticker,
            current_price=request.current_price,
            market_data=request.market_data,
            indicators=request.indicators,
            position_info=None,  # No existing position
            additional_context={"analysis_type": "entry"},
        )
        return await self.analyze(request_with_context)

    async def analyze_exit(self, request: AnalysisRequest) -> TradingDecision:
        """Analyze whether to exit an existing position."""
        # Add exit-specific context
        if request.additional_context:
            context = dict(request.additional_context)
        else:
            context = {}
        context["analysis_type"] = "exit"

        request_with_context = AnalysisRequest(
            ticker=request.ticker,
            current_price=request.current_price,
            market_data=request.market_data,
            indicators=request.indicators,
            position_info=request.position_info,
            additional_context=context,
        )
        return await self.analyze(request_with_context)

    async def get_market_sentiment(
        self,
        ticker: str,
        news_context: Optional[str] = None,
    ) -> str:
        """Get overall market sentiment analysis."""
        try:
            prompt = f"Analyze the current market sentiment for {ticker}."
            if news_context:
                prompt += f"\n\nRecent news context:\n{news_context}"
            prompt += "\n\nRespond with only one word: bullish, bearish, or neutral."

            response = self.client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_completion_tokens=10,
            )

            sentiment = response.choices[0].message.content.strip().lower()
            if sentiment in ["bullish", "bearish", "neutral"]:
                return sentiment
            return "neutral"

        except Exception:
            return "neutral"

    async def validate_signal(
        self,
        request: AnalysisRequest,
        proposed_action: str,
    ) -> bool:
        """Validate a proposed trading signal."""
        try:
            decision = await self.analyze(request)

            if proposed_action.lower() == "buy":
                return decision.decision == DecisionType.BUY
            elif proposed_action.lower() == "sell":
                return decision.decision == DecisionType.SELL

            return False
        except Exception:
            return False

    async def is_available(self) -> bool:
        """Check if AI service is available."""
        try:
            # Test with a simple request
            response = self.client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": "test"}],
                max_completion_tokens=5,
            )
            return response is not None
        except Exception:
            return False

    async def get_remaining_quota(self) -> Optional[int]:
        """Get remaining API quota/tokens."""
        # OpenAI doesn't provide a direct quota check
        return None

    def _get_system_prompt(self) -> str:
        """Get system prompt for trading analysis."""
        return """당신은 **리스크 헌터(Risk Hunter)** 역할의 암호화폐 트레이딩 검증자입니다.
당신의 임무는 이 거래를 **막을 이유를 적극적으로 찾는 것**입니다.
설득력 있는 이유가 없을 때만 거래를 승인하세요.

## ⚠️ 중요 원칙:
- **과거 성과가 미래를 보장하지 않습니다.**
- 백테스팅이 양호해도 시장 국면(Regime) 변화 시 성과가 꺾일 수 있습니다.
- 당신은 '거수기'가 아닙니다. **비판적 시각**을 유지하세요.
- **보수적으로 판단하고 리스크 관리를 최우선**으로 하세요.

## 🎯 핵심 임무: 이 거래를 막을 이유를 찾으세요
1. **시장 국면 변화**: ATR, 거래량, 변동성 패턴이 최근과 다른가?
2. **모멘텀 약화 신호**: RSI 다이버전스, 거래량 감소 등
3. **구조적 위험**: 저항선 근접, BTC 약세 등

## ✅ 안전 조건 체크리스트:
1. 추세 명확: ADX > 25
2. 거래량 확인: 현재 거래량 > 평균의 1.5배
3. 볼린저 밴드: 상단 터치 후 즉시 하락 패턴 아님
4. Regime 일관성: 현재 시장 환경이 최근과 유사

## ⚠️ 위험 조건 (하나라도 있으면 HOLD):
1. BTC 급락 위험: market_risk='high'
2. RSI 다이버전스: 가격↑ but RSI↓
3. 플래시 크래시 감지
4. 거래량-가격 괴리

## 판단 기준:
- **BUY**: 안전 조건 모두 충족 AND 위험 조건 없음 AND 막을 이유 없음
- **SELL**: 포지션 있을 때만 - 손절/익절 조건 충족 시
- **HOLD**: 안전 조건 미충족 OR 위험 조건 존재 OR 막을 이유 1개 이상

## 출력 형식 (반드시 한국어 JSON):
{
  "decision": "buy|sell|hold",
  "reason": "상세 분석 (한국어로 작성)",
  "confidence": "high|medium|low",
  "rejection_reasons": ["거래를 막을 이유 리스트 (있으면)"],
  "safety_conditions_met": {"trend": true/false, "volume": true/false, "bollinger": true/false},
  "risk_conditions_detected": {"btc_risk": true/false, "rsi_divergence": true/false, "flash_crash": true/false},
  "key_indicators": ["주요 지표 리스트"]
}

**중요**: reason 필드는 반드시 한국어로 작성하세요."""

    def _build_analysis_prompt(self, request: AnalysisRequest) -> str:
        """Build analysis prompt from request."""
        coin_symbol = request.ticker.split('-')[1] if '-' in request.ticker else request.ticker

        parts = [
            f"## 분석 요청: {request.ticker} ({coin_symbol})",
            f"\n### 현재 상태:",
            f"- 현재가: {request.current_price:,} KRW",
        ]

        # 포지션 정보
        if request.position_info:
            parts.append("\n### 보유 포지션:")
            parts.append(f"- 진입가: {request.position_info.get('avg_buy_price', 'N/A'):,} KRW")
            parts.append(f"- 현재 수익률: {request.position_info.get('profit_rate', 0):.2f}%")
            parts.append(f"- 보유 수량: {request.position_info.get('balance', 0)}")
        else:
            parts.append("\n### 포지션: 없음 (신규 진입 검토 중)")

        # 기술적 지표
        if request.indicators:
            parts.append("\n### 기술적 지표:")
            if request.indicators.rsi:
                parts.append(f"- RSI: {float(request.indicators.rsi):.1f}")
            if request.indicators.macd and request.indicators.macd_signal:
                parts.append(f"- MACD: {float(request.indicators.macd):.4f}")
                parts.append(f"- MACD Signal: {float(request.indicators.macd_signal):.4f}")
            if request.indicators.bb_upper and request.indicators.bb_middle and request.indicators.bb_lower:
                parts.append(f"- 볼린저 밴드 상단: {float(request.indicators.bb_upper):,.0f}")
                parts.append(f"- 볼린저 밴드 중간: {float(request.indicators.bb_middle):,.0f}")
                parts.append(f"- 볼린저 밴드 하단: {float(request.indicators.bb_lower):,.0f}")
            if request.indicators.sma_20:
                parts.append(f"- SMA20: {float(request.indicators.sma_20):,.0f}")
            if request.indicators.sma_50:
                parts.append(f"- SMA50: {float(request.indicators.sma_50):,.0f}")
            if request.indicators.ema_12 and request.indicators.ema_26:
                parts.append(f"- EMA12: {float(request.indicators.ema_12):,.0f}")
                parts.append(f"- EMA26: {float(request.indicators.ema_26):,.0f}")
            if request.indicators.atr:
                parts.append(f"- ATR: {float(request.indicators.atr):,.0f}")

        # 추가 컨텍스트 (백테스팅, 시장 상관관계 등)
        if request.additional_context:
            # 백테스팅 결과
            if 'backtest_result' in request.additional_context:
                bt = request.additional_context['backtest_result']
                parts.append("\n### 백테스팅 성과 (최근 30일):")
                parts.append(f"- 통과 여부: {'✅ 통과' if bt.get('passed') else '❌ 미통과'}")
                if bt.get('metrics'):
                    metrics = bt['metrics']
                    if 'total_return' in metrics:
                        parts.append(f"- 총 수익률: {metrics['total_return']:.2f}%")
                    if 'win_rate' in metrics:
                        parts.append(f"- 승률: {metrics['win_rate']:.2f}%")
                    if 'sharpe_ratio' in metrics:
                        parts.append(f"- Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
                if bt.get('reason'):
                    parts.append(f"- 사유: {bt['reason']}")

            # 시장 상관관계
            if 'market_correlation' in request.additional_context:
                mc = request.additional_context['market_correlation']
                parts.append("\n### 시장 상관관계:")
                if 'market_risk' in mc:
                    parts.append(f"- 시장 리스크: {mc['market_risk']}")
                if 'btc_correlation' in mc:
                    parts.append(f"- BTC 상관계수: {mc['btc_correlation']:.2f}")

            # 플래시 크래시 감지
            if 'flash_crash' in request.additional_context:
                fc = request.additional_context['flash_crash']
                if fc.get('detected'):
                    parts.append("\n⚠️ **플래시 크래시 감지됨!**")
                    parts.append(f"- 급락률: {fc.get('crash_pct', 0):.2f}%")

            # RSI 다이버전스
            if 'rsi_divergence' in request.additional_context:
                rd = request.additional_context['rsi_divergence']
                if rd.get('detected'):
                    parts.append("\n⚠️ **RSI 다이버전스 감지됨!**")
                    parts.append(f"- 타입: {rd.get('type', 'N/A')}")
                    parts.append(f"- 설명: {rd.get('description', 'N/A')}")

        parts.append("\n### 요청:")
        parts.append("위 정보를 바탕으로 거래를 **막을 이유**를 찾아 분석하고, 한국어 JSON 형식으로 응답하세요.")

        return "\n".join(parts)

    def _parse_decision(self, raw_response: str, ticker: str) -> TradingDecision:
        """Parse AI response into TradingDecision."""
        try:
            # Try to extract JSON from response
            json_start = raw_response.find("{")
            json_end = raw_response.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = raw_response[json_start:json_end]
                data = json.loads(json_str)

                decision_str = data.get("decision", "hold").lower()
                decision_map = {
                    "buy": DecisionType.BUY,
                    "sell": DecisionType.SELL,
                    "hold": DecisionType.HOLD,
                }
                decision = decision_map.get(decision_str, DecisionType.HOLD)

                # confidence 파싱 (문자열 또는 숫자)
                confidence_raw = data.get("confidence", "medium")
                if isinstance(confidence_raw, str):
                    # 문자열을 숫자로 변환
                    confidence_map = {"high": 0.8, "medium": 0.5, "low": 0.3}
                    confidence = Decimal(str(confidence_map.get(confidence_raw.lower(), 0.5)))
                else:
                    confidence = Decimal(str(confidence_raw))

                # rejection_reasons를 key_factors에 포함
                key_factors = data.get("key_indicators", [])
                rejection_reasons = data.get("rejection_reasons", [])
                if rejection_reasons:
                    key_factors.extend([f"[차단 사유] {r}" for r in rejection_reasons])

                # risk_assessment 판정
                risk_detected = data.get("risk_conditions_detected", {})
                if any(risk_detected.values()):
                    risk_assessment = "high"
                else:
                    safety_met = data.get("safety_conditions_met", {})
                    if all(safety_met.values()):
                        risk_assessment = "low"
                    else:
                        risk_assessment = "medium"

                return TradingDecision(
                    decision=decision,
                    confidence=confidence,
                    reasoning=data.get("reason", data.get("reasoning", "")),
                    risk_assessment=risk_assessment,
                    key_factors=key_factors if key_factors else data.get("key_factors", []),
                    raw_response=raw_response,
                )
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

        # Fallback: simple keyword detection
        lower_response = raw_response.lower()
        if "buy" in lower_response and "don't buy" not in lower_response:
            decision = DecisionType.BUY
        elif "sell" in lower_response:
            decision = DecisionType.SELL
        else:
            decision = DecisionType.HOLD

        return TradingDecision(
            decision=decision,
            confidence=Decimal("0.5"),
            reasoning=raw_response[:500],
            raw_response=raw_response,
        )
