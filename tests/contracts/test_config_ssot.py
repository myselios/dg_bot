"""
설정값 단일 소스(SSOT) 계약 테스트

이 테스트가 실패하면 설정값이 여러 곳에 분산 정의되어 있음을 의미합니다.

테스트 분류:
- Blocking: 즉시 통과 필수 (CI 게이트)
- Baseline: 현재 실패 예상 (리팩터링 대상 문서화)
"""
import pytest
from decimal import Decimal

from src.config.settings import ScannerConfig, TradingConfig
from src.domain.value_objects.position_sizing import PositionSizingPolicy
from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage


@pytest.mark.contract
class TestConfigSSOT:
    """설정값 단일 소스 계약"""

    @pytest.mark.baseline  # 현재 실패 예상 (리팩터링 대상)
    def test_scanner_config_is_single_source(self):
        """
        ScannerConfig가 스캐너 설정의 유일한 소스인지 확인

        BASELINE TEST: 현재 실패 예상
        - hybrid_stage.py:52의 DEFAULT_SCANNER_CONFIG 하드코딩과 충돌
        - 이 테스트가 통과하면 SSOT 리팩터링 완료를 의미

        리팩터링 방향:
        1. HybridRiskCheckStage가 ScannerConfig를 직접 참조
        2. DEFAULT_SCANNER_CONFIG 제거
        3. 생성자 기본값을 ScannerConfig로 대체
        """
        # Given: ScannerConfig 값
        expected_liquidity_top_n = ScannerConfig.LIQUIDITY_TOP_N
        expected_backtest_top_n = ScannerConfig.BACKTEST_TOP_N

        # When: HybridRiskCheckStage 기본값
        stage = HybridRiskCheckStage()

        # Then: 기본값이 ScannerConfig와 일치해야 함
        # 불일치 시 설정 분산 문제
        assert stage.scanner_config.get('liquidity_top_n') == expected_liquidity_top_n, \
            f"HybridRiskCheckStage의 liquidity_top_n({stage.scanner_config.get('liquidity_top_n')})이 " \
            f"ScannerConfig({expected_liquidity_top_n})와 불일치"
        assert stage.scanner_config.get('backtest_top_n') == expected_backtest_top_n, \
            f"HybridRiskCheckStage의 backtest_top_n이 ScannerConfig와 불일치"

    def test_position_sizing_is_single_source(self):
        """
        PositionSizingPolicy가 자본 배분의 유일한 소스인지 확인

        검증 항목:
        1. PositionSizingPolicy.default()가 유효한 정책 반환
        2. ExecutionStage가 CalculateEntryAmountUseCase 사용 (레거시 로직 미사용)
        3. TradingConfig.BUY_PERCENTAGE가 실제 사용되지 않음
        """
        from src.trading.pipeline.execution_stage import ExecutionStage
        from unittest.mock import MagicMock

        # 1. PositionSizingPolicy 유효성 검증
        policy = PositionSizingPolicy.default()
        assert policy.max_allocation_ratio is not None, \
            "PositionSizingPolicy가 max_allocation_ratio를 정의해야 함"
        assert policy.max_positions is not None, \
            "PositionSizingPolicy가 max_positions를 정의해야 함"
        assert policy.reserve_ratio is not None, \
            "PositionSizingPolicy가 reserve_ratio를 정의해야 함"

        # 2. ExecutionStage가 UseCase 경로 사용 여부 검증
        stage = ExecutionStage()
        mock_context = MagicMock()
        mock_context.container = MagicMock()  # Container 존재 시 UseCase 경로

        # _has_use_case()가 True 반환해야 함 (Container가 있으므로)
        assert stage._has_use_case(mock_context) is True, \
            "Container가 있을 때 ExecutionStage는 UseCase 경로를 사용해야 함"

        # 3. TradingConfig.BUY_PERCENTAGE 미사용 검증
        # ExecutionStage._calculate_buy_amount()는 deprecated이고 Container가 있으면 호출 안 됨
        trading_config_ratio = getattr(TradingConfig, 'BUY_PERCENTAGE', None)
        if trading_config_ratio is not None:
            # 레거시 설정이 존재해도, UseCase 경로에서는 사용 안 함
            # _calculate_buy_amount 호출 시 DeprecationWarning 발생 확인
            import warnings
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                stage._calculate_buy_amount(1000000)  # 레거시 메서드 호출
                assert len(w) == 1, "deprecated 메서드 호출 시 경고가 발생해야 함"
                assert "deprecated" in str(w[0].message).lower()

    @pytest.mark.baseline  # 현재 실패 예상 (RiskManagementConfig SSOT 리팩터링 대상)
    def test_stop_loss_take_profit_single_source(self):
        """
        손절/익절 설정이 단일 소스인지 확인

        BASELINE TEST: 현재 실패 예상
        - HybridRiskCheckStage 기본값 하드코딩 (-5.0, 10.0)
        - RiskManagementConfig 미존재
        - 이 테스트가 통과하면 SSOT 리팩터링 완료를 의미

        리팩터링 방향:
        1. RiskManagementConfig 추가 (src/config/settings.py)
        2. HybridRiskCheckStage가 RiskManagementConfig 참조
        3. 스케줄러가 RiskManagementConfig 기반으로 파라미터 전달
        """
        # Given: HybridRiskCheckStage 기본값
        stage = HybridRiskCheckStage()

        # Expected: RiskManagementConfig에서 정의된 값
        # (RiskManagementConfig가 없으면 실패)
        try:
            from src.config.settings import RiskManagementConfig
            expected_stop_loss = RiskManagementConfig.POSITION_STOP_LOSS_PCT
            expected_take_profit = RiskManagementConfig.POSITION_TAKE_PROFIT_PCT
        except (ImportError, AttributeError):
            pytest.fail(
                "RiskManagementConfig.POSITION_STOP_LOSS_PCT/TAKE_PROFIT_PCT가 없음 - "
                "SSOT 리팩터링 필요"
            )

        # Then: HybridRiskCheckStage 기본값이 RiskManagementConfig와 일치해야 함
        assert stage.stop_loss_pct == expected_stop_loss, \
            f"손절 비율 불일치: HybridRiskCheckStage({stage.stop_loss_pct}) != RiskManagementConfig({expected_stop_loss})"
        assert stage.take_profit_pct == expected_take_profit, \
            f"익절 비율 불일치: HybridRiskCheckStage({stage.take_profit_pct}) != RiskManagementConfig({expected_take_profit})"
