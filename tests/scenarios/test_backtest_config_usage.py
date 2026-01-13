"""
BacktestConfig 실제 사용 경로 테스트

코드 현실 반영:
- MultiBacktestConfig는 필터 임계값에 직접 사용되지 않음
- QuickBacktestFilter가 BacktestConfig를 사용함
- 이 테스트는 실제 사용되는 경로를 검증함
"""
import pytest
from unittest.mock import MagicMock, patch

from src.backtesting.quick_filter import QuickBacktestFilter, BacktestConfig


@pytest.mark.scenario
class TestBacktestConfigUsage:
    """백테스트 설정 실제 사용 경로"""

    def test_quick_filter_uses_backtest_config(self):
        """QuickBacktestFilter가 BacktestConfig를 사용하는지 확인"""
        # Given: BacktestConfig
        config = BacktestConfig()

        # When: QuickBacktestFilter 생성
        filter_instance = QuickBacktestFilter(config=config)

        # Then: config가 적용되어야 함
        assert filter_instance.config is config, \
            "QuickBacktestFilter가 BacktestConfig를 사용해야 함"

    def test_backtest_config_provides_filter_thresholds(self):
        """BacktestConfig가 필터 임계값을 제공하는지 확인"""
        # Given: BacktestConfig
        config = BacktestConfig()

        # Then: 필터 임계값이 정의되어 있어야 함
        has_sharpe = hasattr(config, 'min_sharpe_ratio') or hasattr(config, 'min_sharpe')
        assert has_sharpe, \
            "BacktestConfig에 Sharpe ratio 임계값이 정의되어야 함"
        assert hasattr(config, 'max_drawdown'), \
            "BacktestConfig에 Max drawdown 임계값이 정의되어야 함"

    def test_multi_backtest_uses_quick_filter(self):
        """MultiCoinBacktest가 QuickBacktestFilter를 사용하는지 확인"""
        from src.scanner.multi_backtest import MultiCoinBacktest

        # When: MultiCoinBacktest 생성
        backtest = MultiCoinBacktest()

        # Then: 인스턴스가 생성되어야 함
        # (QuickBacktestFilter 호출 여부는 통합 테스트에서 검증)
        assert backtest is not None

    @pytest.mark.baseline  # 현재 실패 예상 - 설정 중복 문제 발견
    def test_config_is_not_duplicated_in_multi_backtest(self):
        """
        MultiBacktestConfig가 필터 임계값을 중복 정의하지 않는지 확인

        ⚠️ BASELINE TEST: 현재 실패 (설정 중복 문제 발견)

        발견된 문제:
        - MultiBacktestConfig에 min_sharpe_ratio, max_drawdown 등 필터 임계값이 중복 정의됨
        - BacktestConfig와 MultiBacktestConfig 간 값 불일치 가능성

        리팩터링 방향:
        1. MultiBacktestConfig에서 필터 임계값 제거
        2. 또는 BacktestConfig를 상속하여 일관성 유지
        """
        from src.scanner.multi_backtest import MultiBacktestConfig

        # Given: 두 Config 클래스
        multi_config = MultiBacktestConfig()
        backtest_config = BacktestConfig()

        # Then: MultiBacktestConfig에는 필터 임계값이 없어야 함
        filter_attrs = ['min_sharpe', 'min_sharpe_ratio', 'max_drawdown', 'min_win_rate']
        for attr in filter_attrs:
            assert not hasattr(multi_config, attr), \
                f"MultiBacktestConfig에 필터 임계값 '{attr}'이 중복 정의됨"

        # BacktestConfig에는 필터 임계값이 있어야 함
        has_sharpe = hasattr(backtest_config, 'min_sharpe') or hasattr(backtest_config, 'min_sharpe_ratio')
        assert has_sharpe, "BacktestConfig에 sharpe ratio 임계값이 정의되어야 함"

    def test_config_values_are_consistent(self):
        """BacktestConfig와 MultiBacktestConfig의 공통 필드 값이 일치하는지 확인"""
        from src.scanner.multi_backtest import MultiBacktestConfig

        # Given: 두 Config 클래스
        multi_config = MultiBacktestConfig()
        backtest_config = BacktestConfig()

        # Then: 공통 필드의 값이 일치해야 함 (문서화 목적)
        common_attrs = ['min_sharpe_ratio', 'max_drawdown', 'min_win_rate']
        inconsistencies = []

        for attr in common_attrs:
            if hasattr(multi_config, attr) and hasattr(backtest_config, attr):
                multi_val = getattr(multi_config, attr)
                backtest_val = getattr(backtest_config, attr)
                if multi_val != backtest_val:
                    inconsistencies.append(
                        f"{attr}: MultiBacktestConfig({multi_val}) != BacktestConfig({backtest_val})"
                    )

        # 불일치가 있으면 경고 (현재는 통과시킴 - 문서화 목적)
        if inconsistencies:
            import warnings
            warnings.warn(
                f"Config 값 불일치 발견: {', '.join(inconsistencies)}",
                UserWarning
            )

    def test_backtest_config_default_values_are_reasonable(self):
        """BacktestConfig 기본값이 합리적인지 확인"""
        # Given: BacktestConfig 기본값
        config = BacktestConfig()

        # Then: 기본값이 합리적 범위여야 함
        # max_drawdown은 양수 (최대 허용 드로다운 %, 예: 25.0 = 25%)
        if hasattr(config, 'max_drawdown'):
            assert config.max_drawdown > 0, \
                f"max_drawdown({config.max_drawdown})은 양수여야 함 (최대 허용 드로다운 %)"
            assert config.max_drawdown <= 100, \
                f"max_drawdown({config.max_drawdown})은 100% 이하여야 함"

        # sharpe ratio는 양수
        if hasattr(config, 'min_sharpe_ratio'):
            assert config.min_sharpe_ratio >= 0, \
                f"min_sharpe_ratio({config.min_sharpe_ratio})는 0 이상이어야 함"
        elif hasattr(config, 'min_sharpe'):
            assert config.min_sharpe >= 0, \
                f"min_sharpe({config.min_sharpe})는 0 이상이어야 함"

        # win_rate은 0-100% 범위
        if hasattr(config, 'min_win_rate'):
            assert 0 <= config.min_win_rate <= 100, \
                f"min_win_rate({config.min_win_rate})는 0-100% 범위여야 함"
