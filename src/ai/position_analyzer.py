"""
포지션 관리 분석기 (Position Analyzer) - 하이브리드 방식

포지션이 있을 때 사용하는 관리 전용 분석기입니다.
규칙 기반 우선 + 애매한 상황에서만 AI 호출하는 하이브리드 방식입니다.

역할:
- 기존 포지션 청산 판단 (손절/익절)
- Fakeout, 추세 약화 감지
- 트레일링 스탑 조정 권장
- 부분 익절 판단

비용 최적화:
- 규칙 기반 판단: 무료, 즉시 반응
- AI 분석: 애매한 상황에서만 호출 (비용 절감)
"""
import json
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from openai import OpenAI

from ..config.settings import AIConfig
from ..utils.logger import Logger
from ..utils.helpers import safe_json_dumps


class PositionActionType(Enum):
    """포지션 액션 타입"""
    HOLD = "hold"           # 유지
    EXIT = "exit"           # 전량 청산
    PARTIAL_EXIT = "partial_exit"  # 부분 청산
    ADJUST_STOP = "adjust_stop"    # 스탑 조정


@dataclass
class PositionAction:
    """포지션 관리 액션 결과"""
    action: PositionActionType
    reason: str
    confidence: str = "high"  # 규칙 기반은 항상 high
    trigger: str = ""  # 발동 조건 (stop_loss, take_profit, fakeout 등)
    new_stop_loss: Optional[float] = None  # ADJUST_STOP 시 새 스탑 가격
    exit_ratio: float = 1.0  # PARTIAL_EXIT 시 청산 비율 (0.0-1.0)
    ai_used: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Position:
    """포지션 정보"""
    ticker: str
    entry_price: float
    current_price: float
    amount: float
    entry_time: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    @property
    def profit_rate(self) -> float:
        """수익률 (%)"""
        if self.entry_price <= 0:
            return 0.0
        return ((self.current_price - self.entry_price) / self.entry_price) * 100

    @property
    def profit_loss(self) -> float:
        """손익 금액"""
        return (self.current_price - self.entry_price) * self.amount

    @property
    def holding_hours(self) -> float:
        """보유 시간 (시간)"""
        delta = datetime.now() - self.entry_time
        return delta.total_seconds() / 3600

    @property
    def current_value(self) -> float:
        """현재 평가금액"""
        return self.current_price * self.amount


class PositionAnalyzer:
    """
    하이브리드 포지션 관리 분석기

    1단계: 규칙 기반 체크 (무료, 즉시)
    2단계: 상황 평가 (AI 필요 여부 판단)
    3단계: AI 분석 (애매한 상황만)
    """

    # 규칙 기반 청산 조건 (무료, 즉시)
    DEFAULT_STOP_LOSS_PCT = -5.0
    DEFAULT_TAKE_PROFIT_PCT = 10.0
    FAKEOUT_THRESHOLD_PCT = -2.0
    FAKEOUT_MAX_CANDLES = 3
    TIMEOUT_HOURS = 24
    TIMEOUT_MIN_PROFIT_PCT = 2.0
    ADX_WEAK_THRESHOLD = 20
    ADX_CHECK_MIN_HOURS = 6
    TRAILING_STOP_TRIGGER_PCT = 5.0
    TRAILING_STOP_DISTANCE_PCT = 3.0
    PARTIAL_EXIT_TRIGGER_PCT = 10.0
    PARTIAL_EXIT_RATIO = 0.5

    # AI 분석이 필요한 조건
    AI_NEEDED_PROFIT_RANGE = (2.0, 8.0)
    AI_NEEDED_MIN_HOURS = 6

    @staticmethod
    def _format_number(value: Any, format_str: str = ',.0f') -> str:
        """숫자 포맷팅 헬퍼"""
        if value == 'N/A' or value is None:
            return 'N/A'
        try:
            if isinstance(value, (int, float)):
                return f"{value:{format_str}}"
            return str(value)
        except (ValueError, TypeError):
            return 'N/A'

    def __init__(
        self,
        stop_loss_pct: float = DEFAULT_STOP_LOSS_PCT,
        take_profit_pct: float = DEFAULT_TAKE_PROFIT_PCT
    ):
        """
        Args:
            stop_loss_pct: 손절 비율 (기본 -5%)
            take_profit_pct: 익절 비율 (기본 +10%)
        """
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.client = OpenAI()
        self.model = AIConfig.MODEL

    def analyze(
        self,
        position: Position,
        market_data: Dict[str, Any]
    ) -> PositionAction:
        """
        포지션 관리 분석 (하이브리드)

        Args:
            position: 현재 포지션 정보
            market_data: 시장 데이터 (차트, 지표 등)

        Returns:
            PositionAction: 수행할 액션
        """
        Logger.print_header(f"📊 포지션 관리 분석: {position.ticker}")
        Logger.print_info(f"  진입가: {position.entry_price:,.0f} → 현재가: {position.current_price:,.0f}")
        Logger.print_info(f"  수익률: {position.profit_rate:+.2f}%, 보유: {position.holding_hours:.1f}시간")

        # ═══════════════════════════════════════════════════════════
        # 1단계: 규칙 기반 체크 (무료, 즉시) - 최우선
        # ═══════════════════════════════════════════════════════════
        rule_action = self._check_rule_based_exits(position, market_data)
        if rule_action is not None:
            Logger.print_warning(f"  → 규칙 발동: {rule_action.trigger}")
            return rule_action

        # ═══════════════════════════════════════════════════════════
        # 2단계: 상황 평가 - AI 필요 여부 판단
        # ═══════════════════════════════════════════════════════════
        needs_ai, ai_reason = self._check_needs_ai_analysis(position, market_data)

        if not needs_ai:
            # 명확한 상황 → HOLD (AI 불필요)
            Logger.print_success(f"  → 포지션 유지 (명확한 상황)")
            return PositionAction(
                action=PositionActionType.HOLD,
                reason="규칙 기반 청산 조건 미충족, 추가 분석 불필요",
                ai_used=False
            )

        # ═══════════════════════════════════════════════════════════
        # 3단계: AI 분석 (애매한 상황만)
        # ═══════════════════════════════════════════════════════════
        Logger.print_info(f"  → AI 분석 필요: {ai_reason}")
        return self._analyze_with_ai(position, market_data, ai_reason)

    def _check_rule_based_exits(
        self,
        position: Position,
        market_data: Dict[str, Any]
    ) -> Optional[PositionAction]:
        """
        규칙 기반 청산 조건 체크 (우선순위 순)

        Returns:
            PositionAction if 청산 필요, None if 유지
        """
        profit_rate = position.profit_rate
        holding_hours = position.holding_hours

        # 1. 손절 체크 (최우선)
        if profit_rate <= self.stop_loss_pct:
            return PositionAction(
                action=PositionActionType.EXIT,
                reason=f"손절 발동: 수익률 {profit_rate:.2f}% ≤ {self.stop_loss_pct}%",
                trigger="stop_loss",
                confidence="high",
                ai_used=False,
                metadata={'profit_rate': profit_rate}
            )

        # 2. 익절 체크
        if profit_rate >= self.take_profit_pct:
            return PositionAction(
                action=PositionActionType.EXIT,
                reason=f"익절 발동: 수익률 {profit_rate:.2f}% ≥ {self.take_profit_pct}%",
                trigger="take_profit",
                confidence="high",
                ai_used=False,
                metadata={'profit_rate': profit_rate}
            )

        # 3. 트레일링 스탑 체크 (기존 스탑이 있는 경우)
        if position.stop_loss:
            if position.current_price <= position.stop_loss:
                return PositionAction(
                    action=PositionActionType.EXIT,
                    reason=f"트레일링 스탑 발동: 현재가 {position.current_price:,.0f} ≤ 스탑 {position.stop_loss:,.0f}",
                    trigger="trailing_stop",
                    confidence="high",
                    ai_used=False
                )

        # 4. Fakeout 감지 (진입 후 3봉 내 급락)
        holding_candles = market_data.get('holding_candles', holding_hours)  # 시간봉 기준
        if holding_candles <= self.FAKEOUT_MAX_CANDLES:
            if profit_rate <= self.FAKEOUT_THRESHOLD_PCT:
                return PositionAction(
                    action=PositionActionType.EXIT,
                    reason=f"Fakeout 감지: {holding_candles}봉 내 {profit_rate:.2f}% 하락",
                    trigger="fakeout",
                    confidence="high",
                    ai_used=False,
                    metadata={
                        'holding_candles': holding_candles,
                        'profit_rate': profit_rate
                    }
                )

        # 5. 타임아웃 (24시간 경과 + 수익률 미미)
        if holding_hours >= self.TIMEOUT_HOURS:
            if profit_rate < self.TIMEOUT_MIN_PROFIT_PCT:
                return PositionAction(
                    action=PositionActionType.EXIT,
                    reason=f"타임아웃: {holding_hours:.1f}시간 경과, 수익률 {profit_rate:.2f}% < {self.TIMEOUT_MIN_PROFIT_PCT}%",
                    trigger="timeout",
                    confidence="high",
                    ai_used=False,
                    metadata={
                        'holding_hours': holding_hours,
                        'profit_rate': profit_rate
                    }
                )

        # 6. ADX 약화 (추세 소멸)
        adx = market_data.get('technical_indicators', {}).get('adx', 30)
        if holding_hours >= self.ADX_CHECK_MIN_HOURS:
            if adx < self.ADX_WEAK_THRESHOLD:
                return PositionAction(
                    action=PositionActionType.EXIT,
                    reason=f"추세 약화: ADX {adx:.1f} < {self.ADX_WEAK_THRESHOLD} (보유 {holding_hours:.1f}시간)",
                    trigger="adx_weak",
                    confidence="high",
                    ai_used=False,
                    metadata={'adx': adx, 'holding_hours': holding_hours}
                )

        # 7. 트레일링 스탑 조정 (수익 보호)
        if profit_rate >= self.TRAILING_STOP_TRIGGER_PCT:
            new_stop = position.current_price * (1 - self.TRAILING_STOP_DISTANCE_PCT / 100)
            if position.stop_loss is None or new_stop > position.stop_loss:
                return PositionAction(
                    action=PositionActionType.ADJUST_STOP,
                    reason=f"트레일링 스탑 조정: 수익률 {profit_rate:.2f}%",
                    trigger="trailing_adjustment",
                    new_stop_loss=new_stop,
                    confidence="high",
                    ai_used=False,
                    metadata={
                        'old_stop': position.stop_loss,
                        'new_stop': new_stop,
                        'profit_rate': profit_rate
                    }
                )

        # 8. 부분 익절 (큰 수익 시)
        if profit_rate >= self.PARTIAL_EXIT_TRIGGER_PCT:
            # 부분 익절은 AI 판단으로 넘김 (상황에 따라 다름)
            pass

        return None  # 규칙 기반 청산 조건 없음

    def _check_needs_ai_analysis(
        self,
        position: Position,
        market_data: Dict[str, Any]
    ) -> tuple:
        """
        AI 분석 필요 여부 판단

        Returns:
            (needs_ai: bool, reason: str)
        """
        profit_rate = position.profit_rate
        holding_hours = position.holding_hours

        # 조건 1: 애매한 수익 구간 + 보유 시간
        min_profit, max_profit = self.AI_NEEDED_PROFIT_RANGE
        if min_profit < profit_rate < max_profit and holding_hours > self.AI_NEEDED_MIN_HOURS:
            return True, f"애매한 수익 구간 ({profit_rate:.1f}%), {holding_hours:.1f}시간 보유"

        # 조건 2: 추세 약화 조짐 (ADX 25-30)
        adx = market_data.get('technical_indicators', {}).get('adx', 30)
        if 20 <= adx < 30 and holding_hours > 4:
            return True, f"추세 약화 조짐 (ADX: {adx:.1f})"

        # 조건 3: 거래량-가격 괴리
        volume_analysis = market_data.get('volume_analysis', {})
        volume_trend = volume_analysis.get('volume_trend', 'stable')
        if volume_trend == 'decreasing' and profit_rate > 0:
            return True, "거래량 감소 중 (상승 지속 가능성 검토)"

        # 조건 4: RSI 다이버전스 조짐
        rsi_divergence = market_data.get('rsi_divergence', {})
        if rsi_divergence.get('detected', False):
            return True, "RSI 다이버전스 감지"

        # 조건 5: 부분 익절 판단 필요
        if profit_rate >= self.PARTIAL_EXIT_TRIGGER_PCT:
            return True, f"부분 익절 판단 필요 (수익률 {profit_rate:.1f}%)"

        return False, ""

    def _analyze_with_ai(
        self,
        position: Position,
        market_data: Dict[str, Any],
        analysis_reason: str
    ) -> PositionAction:
        """
        AI를 사용한 포지션 분석

        Args:
            position: 포지션 정보
            market_data: 시장 데이터
            analysis_reason: AI 분석이 필요한 이유

        Returns:
            PositionAction: AI 판단 결과
        """
        system_prompt = self._build_position_system_prompt(position, analysis_reason)
        user_prompt = self._build_position_user_prompt(position, market_data)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )

            ai_response = response.choices[0].message.content
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            Logger.print_info(f"[{timestamp}] 포지션 AI 분석 완료")
            Logger.print_ai_response(timestamp, ai_response)

            decision_data = json.loads(ai_response)

            # AI 결과를 PositionAction으로 변환
            return self._parse_ai_decision(decision_data, position)

        except json.JSONDecodeError as e:
            Logger.print_error(f"포지션 AI 응답 파싱 실패: {str(e)}")
            return PositionAction(
                action=PositionActionType.HOLD,
                reason="AI 응답 파싱 실패 - 안전하게 유지",
                ai_used=True
            )
        except Exception as e:
            Logger.print_error(f"포지션 AI 분석 실패: {str(e)}")
            return PositionAction(
                action=PositionActionType.HOLD,
                reason=f"AI 분석 실패: {str(e)} - 안전하게 유지",
                ai_used=True
            )

    def _build_position_system_prompt(
        self,
        position: Position,
        analysis_reason: str
    ) -> str:
        """포지션 관리용 시스템 프롬프트"""
        return f"""당신은 **포지션 매니저** 역할입니다.
기존 보유 포지션의 관리 방법을 판단하세요.

## 현재 포지션 상태
- 코인: {position.ticker}
- 진입가: {position.entry_price:,.0f} KRW
- 현재가: {position.current_price:,.0f} KRW
- 수익률: {position.profit_rate:+.2f}%
- 보유 시간: {position.holding_hours:.1f}시간
- 평가금액: {position.current_value:,.0f} KRW

## 분석 필요 이유
{analysis_reason}

## 판단 옵션
1. **HOLD**: 포지션 유지 (추세 유효, 청산 이유 없음)
2. **EXIT**: 전량 청산 (추세 반전, 위험 신호)
3. **PARTIAL_EXIT**: 부분 청산 (이익 실현 + 추가 상승 기대)
4. **ADJUST_STOP**: 스탑 조정 (수익 보호)

## 판단 기준
- 추세가 여전히 유효한가?
- 청산해야 할 위험 신호가 있는가?
- 부분 익절로 리스크를 줄일 수 있는가?
- 트레일링 스탑을 조정해야 하는가?

## 출력 형식 (한국어 JSON):
{{
  "action": "hold|exit|partial_exit|adjust_stop",
  "reason": "판단 근거 (한국어)",
  "confidence": "high|medium|low",
  "exit_ratio": 0.5,  // partial_exit 시 청산 비율
  "new_stop_price": 5000000,  // adjust_stop 시 새 스탑 가격
  "risk_factors": ["위험 요소 리스트"],
  "holding_factors": ["유지 근거 리스트"]
}}"""

    def _build_position_user_prompt(
        self,
        position: Position,
        market_data: Dict[str, Any]
    ) -> str:
        """포지션 관리용 사용자 프롬프트"""
        prompt = f"""## 포지션 관리 분석 요청

### 포지션 정보
- 코인: {position.ticker}
- 진입가: {position.entry_price:,.0f} KRW
- 현재가: {position.current_price:,.0f} KRW
- 수익률: {position.profit_rate:+.2f}%
- 손익: {position.profit_loss:+,.0f} KRW
- 보유 시간: {position.holding_hours:.1f}시간
"""

        # 기술적 지표
        if 'technical_indicators' in market_data:
            indicators = market_data['technical_indicators']
            prompt += f"""
### 기술적 지표
- RSI: {self._format_number(indicators.get('rsi'), '.1f')}
- MACD: {self._format_number(indicators.get('macd'), '.2f')}
- ADX: {self._format_number(indicators.get('adx'), '.1f')}
- +DI: {self._format_number(indicators.get('plus_di'), '.1f')}
- -DI: {self._format_number(indicators.get('minus_di'), '.1f')}
"""

        # 거래량 분석
        if 'volume_analysis' in market_data:
            vol = market_data['volume_analysis']
            prompt += f"""
### 거래량 분석
- 거래량 추세: {vol.get('volume_trend', 'N/A')}
- 거래량 비율: {self._format_number(vol.get('volume_ratio'), '.2f')}x
- 매수 압력: {self._format_number(vol.get('buying_pressure'), '.1f')}/100
"""

        # RSI 다이버전스
        if 'rsi_divergence' in market_data:
            div = market_data['rsi_divergence']
            if div.get('detected', False):
                prompt += f"""
### RSI 다이버전스 감지
- 유형: {div.get('type', 'N/A')}
- 신뢰도: {div.get('strength', 'N/A')}
"""

        # 시장 상관관계
        if 'market_correlation' in market_data:
            corr = market_data['market_correlation']
            prompt += f"""
### 시장 상관관계
- BTC 상관계수: {self._format_number(corr.get('btc_correlation'), '.2f')}
- 시장 리스크: {corr.get('market_risk', 'N/A')}
"""

        prompt += """
### 분석 요청
위 데이터를 바탕으로 포지션 관리 방법을 판단하세요.
반드시 한국어 JSON 형식으로 응답하세요."""

        return prompt

    def _parse_ai_decision(
        self,
        decision_data: Dict,
        position: Position
    ) -> PositionAction:
        """AI 결과를 PositionAction으로 변환"""
        action_str = decision_data.get('action', 'hold').lower()

        action_map = {
            'hold': PositionActionType.HOLD,
            'exit': PositionActionType.EXIT,
            'partial_exit': PositionActionType.PARTIAL_EXIT,
            'adjust_stop': PositionActionType.ADJUST_STOP
        }

        action_type = action_map.get(action_str, PositionActionType.HOLD)

        return PositionAction(
            action=action_type,
            reason=decision_data.get('reason', 'AI 판단'),
            confidence=decision_data.get('confidence', 'medium'),
            trigger='ai_analysis',
            new_stop_loss=decision_data.get('new_stop_price'),
            exit_ratio=decision_data.get('exit_ratio', 1.0),
            ai_used=True,
            metadata={
                'risk_factors': decision_data.get('risk_factors', []),
                'holding_factors': decision_data.get('holding_factors', [])
            }
        )

    def analyze_multiple_positions(
        self,
        positions: List[Position],
        market_data_map: Dict[str, Dict]
    ) -> Dict[str, PositionAction]:
        """
        여러 포지션 동시 분석

        Args:
            positions: 포지션 리스트
            market_data_map: {ticker: market_data} 맵

        Returns:
            {ticker: PositionAction} 맵
        """
        results = {}

        for position in positions:
            market_data = market_data_map.get(position.ticker, {})
            action = self.analyze(position, market_data)
            results[position.ticker] = action

        return results
