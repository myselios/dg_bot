"""
AI 판단 검증 모듈

GPT-4의 응답을 맹목적으로 신뢰하지 않고, 룰 기반 검증을 통해
논리적 모순이나 위험한 판단을 차단합니다.

퀀트 투자 원칙: "Trust, but Verify"
"""
from typing import Dict, Any, Optional, Tuple
from ..utils.logger import Logger
from ..config.settings import TrendFilterConfig


class AIDecisionValidator:
    """AI 판단 검증기"""

    @staticmethod
    def validate_decision(
        decision: Dict[str, Any],
        indicators: Dict[str, float],
        market_conditions: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        AI 판단의 논리적 정합성 검증

        Args:
            decision: AI 판단 결과 {'decision': 'buy|sell|hold', 'reason': '...', 'confidence': '...'}
            indicators: 기술적 지표 딕셔너리
            market_conditions: 시장 조건 (market_correlation, flash_crash 등)

        Returns:
            (유효 여부, 검증 결과 메시지, 오버라이드 결정)
            - 유효: (True, "검증 통과", None)
            - 무효: (False, "검증 실패 사유", "hold")
        """
        ai_decision = decision.get('decision', 'hold').lower()
        ai_reason = decision.get('reason', '')
        ai_confidence = decision.get('confidence', 'unknown').lower()

        # ============================================
        # 1. RSI 모순 체크
        # ============================================
        rsi_check = AIDecisionValidator._check_rsi_contradiction(
            ai_decision, indicators
        )
        if not rsi_check[0]:
            return rsi_check

        # ============================================
        # 2. 변동성 체크
        # ============================================
        volatility_check = AIDecisionValidator._check_volatility(
            ai_decision, indicators
        )
        if not volatility_check[0]:
            return volatility_check

        # ============================================
        # 3. 시장 환경 체크 (Phase 2: BTC 리스크, 플래시 크래시)
        # ============================================
        if market_conditions:
            market_check = AIDecisionValidator._check_market_environment(
                ai_decision, market_conditions
            )
            if not market_check[0]:
                return market_check

        # ============================================
        # 4. Fakeout 체크 (변동성 돌파 전략 전용)
        # ============================================
        fakeout_check = AIDecisionValidator._check_fakeout(
            ai_decision, indicators
        )
        if not fakeout_check[0]:
            return fakeout_check

        # ============================================
        # 5. 복합 트렌드 필터 체크 (ADX + 거래량 + 볼린저 밴드)
        # ============================================
        trend_filter_check = AIDecisionValidator._check_trend_filter(
            ai_decision, indicators
        )
        if not trend_filter_check[0]:
            return trend_filter_check

        # ============================================
        # 6. 신뢰도 검증
        # ============================================
        confidence_check = AIDecisionValidator._check_confidence(
            ai_decision, ai_confidence
        )
        if not confidence_check[0]:
            return confidence_check

        # 모든 검증 통과
        return True, "AI 판단 검증 통과", None

    @staticmethod
    def _check_rsi_contradiction(
        ai_decision: str,
        indicators: Dict[str, float]
    ) -> Tuple[bool, str, Optional[str]]:
        """RSI 모순 체크"""
        rsi = indicators.get('rsi', 50)

        # 매수 신호인데 RSI 과매수 (70 이상)
        if ai_decision == 'buy' and rsi > 70:
            reason = f"❌ AI는 BUY지만 RSI {rsi:.1f} 과매수 → 진입 위험"
            Logger.print_warning(reason)
            return False, reason, 'hold'

        # 매도 신호인데 RSI 과매도 (30 이하)
        if ai_decision == 'sell' and rsi < 30:
            reason = f"❌ AI는 SELL이지만 RSI {rsi:.1f} 과매도 → 반등 가능성"
            Logger.print_warning(reason)
            return False, reason, 'hold'

        return True, "RSI 정합성 확인", None

    @staticmethod
    def _check_volatility(
        ai_decision: str,
        indicators: Dict[str, float]
    ) -> Tuple[bool, str, Optional[str]]:
        """변동성 체크 - ATR 기반"""
        atr_percent = indicators.get('atr_percent', 0)

        # 매수 신호인데 고변동성 (6% 이상)
        if ai_decision == 'buy' and atr_percent > 6.0:
            reason = f"❌ AI는 BUY지만 ATR {atr_percent:.1f}% 고변동성 → 리스크 과다"
            Logger.print_warning(reason)
            return False, reason, 'hold'

        return True, "변동성 정상", None

    @staticmethod
    def _check_market_environment(
        ai_decision: str,
        market_conditions: Dict[str, Any]
    ) -> Tuple[bool, str, Optional[str]]:
        """시장 환경 체크"""
        # 1. BTC 시장 리스크 체크
        market_corr = market_conditions.get('market_correlation', {})
        if market_corr.get('market_risk') == 'high' and ai_decision == 'buy':
            reason = f"❌ BTC 시장 리스크 높음: {market_corr.get('risk_reason', 'N/A')}"
            Logger.print_warning(reason)
            return False, reason, 'hold'

        # 2. 플래시 크래시 체크
        flash_crash = market_conditions.get('flash_crash', {})
        if flash_crash.get('detected') and ai_decision == 'buy':
            reason = f"❌ 플래시 크래시 감지: {flash_crash.get('description', 'N/A')}"
            Logger.print_warning(reason)
            return False, reason, 'hold'

        # 3. RSI 하락 다이버전스 체크
        rsi_div = market_conditions.get('rsi_divergence', {})
        if rsi_div.get('type') == 'bearish_divergence' and ai_decision == 'buy':
            reason = f"❌ RSI 하락 다이버전스: {rsi_div.get('description', 'N/A')}"
            Logger.print_warning(reason)
            return False, reason, 'hold'

        return True, "시장 환경 안전", None

    @staticmethod
    def _check_fakeout(
        ai_decision: str,
        indicators: Dict[str, float]
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Fakeout(가짜 돌파) 체크

        진짜 돌파 조건:
        1. 거래량이 평균의 1.5배 이상
        2. 추세 강도(ADX) > 25
        """
        if ai_decision != 'buy':
            return True, "매수 신호 아님", None

        # 거래량 체크 (강화: 1.3배 → 1.5배)
        volume_ratio = indicators.get('volume_ratio', 0)
        if volume_ratio < 1.5:
            reason = f"❌ Fakeout 의심: 거래량 {volume_ratio:.2f}x < 1.5x"
            Logger.print_warning(reason)
            return False, reason, 'hold'

        # ADX 체크 (추세 강도)
        adx = indicators.get('adx', 0)
        if adx < 20:
            reason = f"❌ Fakeout 의심: ADX {adx:.1f} < 20 (약한 추세)"
            Logger.print_warning(reason)
            return False, reason, 'hold'

        return True, "진짜 돌파 확인", None

    @staticmethod
    def _check_trend_filter(
        ai_decision: str,
        indicators: Dict[str, float]
    ) -> Tuple[bool, str, Optional[str]]:
        """
        복합 트렌드 필터 (ADX + 거래량 + 볼린저 밴드)

        검증 조건 (설정값 참조):
        1. ADX >= MIN_ADX: 강한 트렌드 확인
        2. 거래량 >= 평균의 MIN_VOLUME_RATIO배
        3. 볼린저 밴드 확장 중 (BB Width > MIN_BB_WIDTH_PCT%)
        """
        if ai_decision != 'buy':
            return True, "매수 신호 아님", None

        # 설정값 로드
        min_adx = TrendFilterConfig.MIN_ADX
        min_volume_ratio = TrendFilterConfig.MIN_VOLUME_RATIO
        min_bb_width_pct = TrendFilterConfig.MIN_BB_WIDTH_PCT

        # 1. ADX 트렌드 강도 체크
        adx = indicators.get('adx', 0)
        if adx < min_adx:
            reason = f"❌ 트렌드 강도 부족: ADX {adx:.1f} < {min_adx}"
            Logger.print_warning(reason)
            return False, reason, 'hold'

        # 2. 거래량 체크
        volume_ratio = indicators.get('volume_ratio', 0)
        if volume_ratio < min_volume_ratio:
            reason = f"❌ 거래량 부족: {volume_ratio:.2f}x < {min_volume_ratio}x"
            Logger.print_warning(reason)
            return False, reason, 'hold'

        # 3. 볼린저 밴드 확장 체크
        bb_width_pct = indicators.get('bb_width_pct', 0)
        if bb_width_pct < min_bb_width_pct:
            reason = f"❌ 볼린저 밴드 수축: {bb_width_pct:.2f}% < {min_bb_width_pct}%"
            Logger.print_warning(reason)
            return False, reason, 'hold'

        return True, "트렌드 필터 통과", None

    @staticmethod
    def _check_confidence(
        ai_decision: str,
        ai_confidence: str
    ) -> Tuple[bool, str, Optional[str]]:
        """
        AI 신뢰도 체크

        low 신뢰도 시 매매 금지
        """
        if ai_decision in ['buy', 'sell'] and ai_confidence == 'low':
            reason = f"❌ AI 신뢰도 낮음: {ai_confidence} → 거래 중단"
            Logger.print_warning(reason)
            return False, reason, 'hold'

        return True, "신뢰도 정상", None

    @staticmethod
    def generate_validation_report(
        validation_result: Tuple[bool, str, Optional[str]],
        decision: Dict[str, Any],
        indicators: Dict[str, float]
    ) -> str:
        """검증 결과 리포트 생성"""
        is_valid, reason, override = validation_result

        report = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 AI 판단 검증 결과
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
원본 AI 판단: {decision.get('decision', 'N/A').upper()}
AI 신뢰도: {decision.get('confidence', 'N/A').upper()}

검증 상태: {"✅ 통과" if is_valid else "❌ 실패"}
검증 사유: {reason}
최종 결정: {override.upper() if override else decision.get('decision', 'N/A').upper()}

주요 지표:
- RSI: {indicators.get('rsi', 0):.1f}
- ATR: {indicators.get('atr_percent', 0):.2f}%
- Volume Ratio: {indicators.get('volume_ratio', 0):.2f}x
- ADX: {indicators.get('adx', 0):.1f}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        return report
