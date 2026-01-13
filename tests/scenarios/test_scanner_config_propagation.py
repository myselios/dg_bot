"""
ScannerConfig 설정 전파 시나리오 테스트

ScannerConfig에서 정의한 값이 모든 스캐닝 컴포넌트에 전파되는지 검증합니다.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.config.settings import ScannerConfig


@pytest.mark.scenario
class TestScannerConfigPropagation:
    """스캐너 설정 전파 시나리오"""

    def test_scanner_config_reaches_coin_selector(self):
        """ScannerConfig가 CoinSelector에 전달되는지 확인"""
        from src.scanner.coin_selector import CoinSelector

        # Given: ScannerConfig 값
        expected_liquidity = ScannerConfig.LIQUIDITY_TOP_N
        expected_backtest = ScannerConfig.BACKTEST_TOP_N

        # When: CoinSelector 생성 (기본값)
        selector = CoinSelector()

        # Then: ScannerConfig 값이 적용되어야 함
        assert selector.liquidity_top_n == expected_liquidity, \
            f"CoinSelector.liquidity_top_n({selector.liquidity_top_n}) != ScannerConfig({expected_liquidity})"
        assert selector.backtest_top_n == expected_backtest, \
            f"CoinSelector.backtest_top_n({selector.backtest_top_n}) != ScannerConfig({expected_backtest})"

    def test_scanner_config_change_propagates(self):
        """ScannerConfig 변경이 전파되는지 확인"""
        from src.scanner.coin_selector import CoinSelector

        # Given: 변경된 설정값
        custom_backtest_top_n = 7

        # When: 새 인스턴스 생성 (명시적 파라미터)
        selector = CoinSelector(
            backtest_top_n=custom_backtest_top_n
        )

        # Then: 변경값이 적용되어야 함
        assert selector.backtest_top_n == custom_backtest_top_n

    def test_hybrid_stage_uses_scanner_config(self):
        """HybridRiskCheckStage가 ScannerConfig를 사용하는지 확인"""
        from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage

        # Given: ScannerConfig 기반 설정
        scanner_config = {
            'liquidity_top_n': ScannerConfig.LIQUIDITY_TOP_N,
            'backtest_top_n': ScannerConfig.BACKTEST_TOP_N,
            'final_select_n': ScannerConfig.FINAL_SELECT_N,
        }

        # When: 스테이지 생성
        stage = HybridRiskCheckStage(scanner_config=scanner_config)

        # Then: 설정이 적용되어야 함
        assert stage.scanner_config['liquidity_top_n'] == ScannerConfig.LIQUIDITY_TOP_N
        assert stage.scanner_config['backtest_top_n'] == ScannerConfig.BACKTEST_TOP_N

    def test_default_scanner_config_matches_scanner_config(self):
        """HybridRiskCheckStage의 기본값이 ScannerConfig와 일치하는지 확인"""
        from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage

        # Given: 기본값으로 생성
        stage = HybridRiskCheckStage()

        # Then: DEFAULT_SCANNER_CONFIG가 ScannerConfig와 일치해야 함
        # (현재 값이 일치하는지 문서화)
        expected_liquidity = ScannerConfig.LIQUIDITY_TOP_N
        expected_backtest = ScannerConfig.BACKTEST_TOP_N

        actual_liquidity = stage.scanner_config.get('liquidity_top_n')
        actual_backtest = stage.scanner_config.get('backtest_top_n')

        # 이 테스트가 실패하면 DEFAULT_SCANNER_CONFIG 업데이트 필요
        assert actual_liquidity == expected_liquidity, \
            f"DEFAULT_SCANNER_CONFIG.liquidity_top_n({actual_liquidity}) != ScannerConfig({expected_liquidity})"
        assert actual_backtest == expected_backtest, \
            f"DEFAULT_SCANNER_CONFIG.backtest_top_n({actual_backtest}) != ScannerConfig({expected_backtest})"
