"""
AI 판단 검증기 테스트
TDD 원칙: 테스트 케이스를 먼저 작성하고 구현을 검증합니다.
"""
import pytest
from src.ai.validator import AIDecisionValidator


class TestAIDecisionValidator:
    """AIDecisionValidator 클래스 테스트"""

    def get_passing_indicators(self):
        """모든 검증 통과하는 지표 반환"""
        return {
            'rsi': 50.0,
            'atr_percent': 3.0,
            'volume_ratio': 2.0,  # >= 1.5 (fakeout, trend_filter)
            'adx': 30.0,  # >= 25 (trend_filter)
            'bb_width_pct': 5.0,  # >= 4.0 (trend_filter)
            'macd': 100.0
        }

    @pytest.fixture
    def sample_indicators(self):
        """샘플 기술적 지표 (모든 검증 통과용)"""
        return self.get_passing_indicators()

    @pytest.fixture
    def sample_decision(self):
        """샘플 AI 판단"""
        return {
            'decision': 'buy',
            'confidence': 'high',
            'reason': '상승 추세 확인'
        }

    # ============================================
    # validate_decision() 전체 통합 테스트
    # ============================================

    @pytest.mark.unit
    def test_validate_decision_all_pass(self):
        """모든 검증 통과 테스트"""
        # Given - 모든 조건을 충족하는 지표
        decision = {
            'decision': 'buy',
            'confidence': 'high',
            'reason': '상승 추세 확인'
        }
        indicators = self.get_passing_indicators()

        market_conditions = {
            'market_correlation': {'market_risk': 'low'},
            'flash_crash': {'detected': False},
            'rsi_divergence': {'type': 'none'}
        }

        # When
        is_valid, reason, override = AIDecisionValidator.validate_decision(
            decision,
            indicators,
            market_conditions
        )

        # Then
        assert is_valid is True
        assert '통과' in reason
        assert override is None

    @pytest.mark.unit
    def test_validate_decision_hold_no_validation_needed(self, sample_indicators):
        """HOLD 판단은 검증 불필요"""
        # Given
        decision = {
            'decision': 'hold',
            'confidence': 'medium',
            'reason': '관망'
        }

        # When
        is_valid, reason, override = AIDecisionValidator.validate_decision(
            decision,
            sample_indicators,
            None
        )

        # Then
        assert is_valid is True

    # ============================================
    # RSI 모순 체크 테스트
    # ============================================

    @pytest.mark.unit
    def test_check_rsi_contradiction_buy_overbought(self, sample_decision, sample_indicators):
        """매수 신호 + RSI 과매수 (70+) 테스트"""
        # Given
        sample_indicators['rsi'] = 75.0  # 과매수

        # When
        is_valid, reason, override = AIDecisionValidator.validate_decision(
            sample_decision,
            sample_indicators,
            None
        )

        # Then
        assert is_valid is False
        assert 'RSI' in reason
        assert '과매수' in reason
        assert override == 'hold'

    @pytest.mark.unit
    def test_check_rsi_contradiction_sell_oversold(self, sample_indicators):
        """매도 신호 + RSI 과매도 (30-) 테스트"""
        # Given
        decision = {'decision': 'sell', 'confidence': 'high', 'reason': ''}
        sample_indicators['rsi'] = 25.0  # 과매도

        # When
        is_valid, reason, override = AIDecisionValidator.validate_decision(
            decision,
            sample_indicators,
            None
        )

        # Then
        assert is_valid is False
        assert 'RSI' in reason
        assert '과매도' in reason
        assert override == 'hold'

    @pytest.mark.unit
    def test_check_rsi_normal_range(self):
        """RSI 정상 범위 (30~70) 테스트"""
        # Given - RSI 정상 범위 + 모든 조건 충족
        decision = {
            'decision': 'buy',
            'confidence': 'high',
            'reason': '상승 추세 확인'
        }
        indicators = self.get_passing_indicators()
        indicators['rsi'] = 55.0  # 정상

        # When
        is_valid, reason, override = AIDecisionValidator.validate_decision(
            decision,
            indicators,
            None
        )

        # Then
        assert is_valid is True

    # ============================================
    # 변동성 체크 테스트
    # ============================================

    @pytest.mark.unit
    def test_check_volatility_high_atr(self, sample_decision, sample_indicators):
        """고변동성 (ATR 6%+) 테스트"""
        # Given
        sample_indicators['atr_percent'] = 7.5  # 고변동성

        # When
        is_valid, reason, override = AIDecisionValidator.validate_decision(
            sample_decision,
            sample_indicators,
            None
        )

        # Then
        assert is_valid is False
        assert 'ATR' in reason
        assert '고변동성' in reason
        assert override == 'hold'

    @pytest.mark.unit
    def test_check_volatility_normal_atr(self):
        """정상 변동성 테스트"""
        # Given - 정상 변동성 + 모든 조건 충족
        decision = {
            'decision': 'buy',
            'confidence': 'high',
            'reason': '상승 추세 확인'
        }
        indicators = self.get_passing_indicators()
        indicators['atr_percent'] = 4.0  # 정상

        # When
        is_valid, reason, override = AIDecisionValidator.validate_decision(
            decision,
            indicators,
            None
        )

        # Then
        assert is_valid is True

    # ============================================
    # 시장 환경 체크 테스트
    # ============================================

    @pytest.mark.unit
    def test_check_market_environment_btc_high_risk(self, sample_decision, sample_indicators):
        """BTC 시장 리스크 높음 테스트"""
        # Given
        market_conditions = {
            'market_correlation': {
                'market_risk': 'high',
                'risk_reason': 'BTC 급락 중'
            },
            'flash_crash': {'detected': False},
            'rsi_divergence': {'type': 'none'}
        }

        # When
        is_valid, reason, override = AIDecisionValidator.validate_decision(
            sample_decision,
            sample_indicators,
            market_conditions
        )

        # Then
        assert is_valid is False
        assert 'BTC' in reason
        assert override == 'hold'

    @pytest.mark.unit
    def test_check_market_environment_flash_crash(self, sample_decision, sample_indicators):
        """플래시 크래시 감지 테스트"""
        # Given
        market_conditions = {
            'market_correlation': {'market_risk': 'low'},
            'flash_crash': {
                'detected': True,
                'description': '5분 내 -10% 급락'
            },
            'rsi_divergence': {'type': 'none'}
        }

        # When
        is_valid, reason, override = AIDecisionValidator.validate_decision(
            sample_decision,
            sample_indicators,
            market_conditions
        )

        # Then
        assert is_valid is False
        assert '플래시 크래시' in reason
        assert override == 'hold'

    @pytest.mark.unit
    def test_check_market_environment_bearish_divergence(self, sample_decision, sample_indicators):
        """RSI 하락 다이버전스 테스트"""
        # Given
        market_conditions = {
            'market_correlation': {'market_risk': 'low'},
            'flash_crash': {'detected': False},
            'rsi_divergence': {
                'type': 'bearish_divergence',
                'description': '가격 상승하나 RSI 하락'
            }
        }

        # When
        is_valid, reason, override = AIDecisionValidator.validate_decision(
            sample_decision,
            sample_indicators,
            market_conditions
        )

        # Then
        assert is_valid is False
        assert 'RSI 하락 다이버전스' in reason
        assert override == 'hold'

    # ============================================
    # Fakeout 체크 테스트
    # ============================================

    @pytest.mark.unit
    def test_check_fakeout_low_volume(self, sample_decision, sample_indicators):
        """낮은 거래량 (Fakeout 의심) 테스트"""
        # Given
        sample_indicators['volume_ratio'] = 1.1  # 1.3x 미만

        # When
        is_valid, reason, override = AIDecisionValidator.validate_decision(
            sample_decision,
            sample_indicators,
            None
        )

        # Then
        assert is_valid is False
        assert 'Fakeout' in reason
        assert '거래량' in reason
        assert override == 'hold'

    @pytest.mark.unit
    def test_check_fakeout_weak_trend(self, sample_decision, sample_indicators):
        """약한 추세 (ADX < 20) 테스트"""
        # Given
        sample_indicators['adx'] = 15.0  # 약한 추세

        # When
        is_valid, reason, override = AIDecisionValidator.validate_decision(
            sample_decision,
            sample_indicators,
            None
        )

        # Then
        assert is_valid is False
        assert 'Fakeout' in reason or 'ADX' in reason
        assert override == 'hold'

    @pytest.mark.unit
    def test_check_fakeout_strong_signal(self):
        """진짜 돌파 (거래량 충분 + ADX 높음) 테스트"""
        # Given - 모든 조건 충족
        decision = {
            'decision': 'buy',
            'confidence': 'high',
            'reason': '상승 추세 확인'
        }
        indicators = self.get_passing_indicators()
        indicators['volume_ratio'] = 2.0  # 충분 >= 1.5
        indicators['adx'] = 35.0  # 강한 추세 >= 25
        indicators['bb_width_pct'] = 5.0  # BB 확장 >= 4.0

        # When
        is_valid, reason, override = AIDecisionValidator.validate_decision(
            decision,
            indicators,
            None
        )

        # Then
        assert is_valid is True

    # ============================================
    # 신뢰도 체크 테스트
    # ============================================

    @pytest.mark.unit
    def test_check_confidence_low_for_buy(self):
        """낮은 신뢰도 매수 신호 테스트"""
        # Given - 모든 지표는 통과하지만 신뢰도가 낮음
        decision = {
            'decision': 'buy',
            'confidence': 'low',  # 낮은 신뢰도
            'reason': ''
        }
        indicators = self.get_passing_indicators()

        # When
        is_valid, reason, override = AIDecisionValidator.validate_decision(
            decision,
            indicators,
            None
        )

        # Then
        assert is_valid is False
        assert '신뢰도' in reason
        assert override == 'hold'

    @pytest.mark.unit
    def test_check_confidence_low_for_sell(self, sample_indicators):
        """낮은 신뢰도 매도 신호 테스트"""
        # Given
        decision = {
            'decision': 'sell',
            'confidence': 'low',
            'reason': ''
        }

        # When
        is_valid, reason, override = AIDecisionValidator.validate_decision(
            decision,
            sample_indicators,
            None
        )

        # Then
        assert is_valid is False
        assert '신뢰도' in reason
        assert override == 'hold'

    @pytest.mark.unit
    def test_check_confidence_high(self):
        """높은 신뢰도 테스트"""
        # Given - 모든 조건 충족
        decision = {
            'decision': 'buy',
            'confidence': 'high',
            'reason': '상승 추세 확인'
        }
        indicators = self.get_passing_indicators()

        # When
        is_valid, reason, override = AIDecisionValidator.validate_decision(
            decision,
            indicators,
            None
        )

        # Then
        assert is_valid is True

    # ============================================
    # 검증 리포트 생성 테스트
    # ============================================

    @pytest.mark.unit
    def test_generate_validation_report_success(self, sample_decision, sample_indicators):
        """검증 성공 리포트 생성 테스트"""
        # Given
        validation_result = (True, "검증 통과", None)

        # When
        report = AIDecisionValidator.generate_validation_report(
            validation_result,
            sample_decision,
            sample_indicators
        )

        # Then
        assert '검증 결과' in report
        assert 'BUY' in report
        assert '✅ 통과' in report
        assert 'RSI' in report

    @pytest.mark.unit
    def test_generate_validation_report_failure(self, sample_decision, sample_indicators):
        """검증 실패 리포트 생성 테스트"""
        # Given
        validation_result = (False, "RSI 과매수", 'hold')

        # When
        report = AIDecisionValidator.generate_validation_report(
            validation_result,
            sample_decision,
            sample_indicators
        )

        # Then
        assert '검증 결과' in report
        assert '❌ 실패' in report
        assert 'RSI 과매수' in report  # 수정: reason -> report
        assert 'HOLD' in report  # override된 결정

    # ============================================
    # 복합 시나리오 테스트
    # ============================================

    @pytest.mark.unit
    def test_multiple_violations(self, sample_decision, sample_indicators):
        """여러 검증 실패 조건이 동시에 있을 때 (첫 번째 실패만 반환)"""
        # Given
        sample_indicators['rsi'] = 75.0  # RSI 과매수
        sample_indicators['atr_percent'] = 8.0  # 고변동성
        market_conditions = {
            'market_correlation': {'market_risk': 'high'},  # BTC 리스크
            'flash_crash': {'detected': False},
            'rsi_divergence': {'type': 'none'}
        }

        # When
        is_valid, reason, override = AIDecisionValidator.validate_decision(
            sample_decision,
            sample_indicators,
            market_conditions
        )

        # Then
        assert is_valid is False
        assert override == 'hold'
        # 첫 번째 검증 실패 (RSI)가 반환되어야 함
        assert 'RSI' in reason

    @pytest.mark.unit
    def test_edge_case_missing_indicators(self, sample_decision):
        """지표 데이터 누락 시 처리 테스트"""
        # Given
        incomplete_indicators = {
            'rsi': 50.0
            # atr_percent, volume_ratio, adx 누락
        }

        # When
        is_valid, reason, override = AIDecisionValidator.validate_decision(
            sample_decision,
            incomplete_indicators,
            None
        )

        # Then
        # 누락된 지표는 기본값으로 처리되어 검증 통과 또는 안전하게 실패
        assert is_valid is not None  # 에러 발생 안 함
        assert isinstance(reason, str)
