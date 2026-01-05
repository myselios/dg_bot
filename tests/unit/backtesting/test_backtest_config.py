"""
BacktestConfig 단위 테스트

TradingPassConfig와 ResearchPassConfig를 통합한 BacktestConfig의
기본 동작을 검증합니다.
"""
import pytest
from src.backtesting.quick_filter import BacktestConfig


class TestBacktestConfig:
    """BacktestConfig 테스트 클래스"""

    def test_backtest_config_default_values(self):
        """기본값으로 BacktestConfig 생성 테스트"""
        config = BacktestConfig()

        # 백테스팅 기본 설정
        assert config.days == 730
        assert config.use_local_data is True
        assert config.initial_capital == 10_000_000
        assert config.commission == 0.0005
        assert config.slippage == 0.0001

        # 수익성 지표 (기존 TradingPassConfig 기준)
        assert config.min_return == 9.0
        assert config.min_win_rate == 35.0
        assert config.min_profit_factor == 1.5

        # 위험조정 수익률
        assert config.min_sharpe_ratio == 0.7
        assert config.min_sortino_ratio == 0.9
        assert config.min_calmar_ratio == 0.4

        # 리스크 관리
        assert config.max_drawdown == 25.0
        assert config.max_consecutive_losses == 6
        assert config.max_volatility == 80.0

        # 통계적 유의성 (Phase 7: 10 → 30, Central Limit Theorem)
        assert config.min_trades == 30

        # 거래 품질
        assert config.min_avg_win_loss_ratio == 1.0
        assert config.max_avg_holding_hours == 240.0

    def test_backtest_config_custom_values(self):
        """커스텀 값으로 BacktestConfig 생성 테스트"""
        config = BacktestConfig(
            days=365,
            min_return=12.0,
            min_win_rate=40.0,
            max_drawdown=20.0
        )

        assert config.days == 365
        assert config.min_return == 12.0
        assert config.min_win_rate == 40.0
        assert config.max_drawdown == 20.0

        # 나머지는 기본값 유지
        assert config.commission == 0.0005
        assert config.min_trades == 30  # Phase 7: 10 → 30

    def test_backtest_config_threshold_ranges(self):
        """임계값 범위 검증 테스트"""
        config = BacktestConfig()

        # 수익성 지표는 양수
        assert config.min_return >= 0
        assert config.min_win_rate >= 0
        assert config.min_profit_factor >= 0

        # 위험조정 수익률은 음수가 아님
        assert config.min_sharpe_ratio >= 0
        assert config.min_sortino_ratio >= 0
        assert config.min_calmar_ratio >= 0

        # 리스크 관리 지표
        assert config.max_drawdown > 0
        assert config.max_consecutive_losses > 0
        assert config.max_volatility > 0

        # 통계적 유의성
        assert config.min_trades > 0

        # 거래 품질
        assert config.min_avg_win_loss_ratio >= 0
        assert config.max_avg_holding_hours > 0

    def test_backtest_config_commission_and_slippage_positive(self):
        """수수료와 슬리피지는 양수여야 함"""
        config = BacktestConfig()

        assert config.commission > 0
        assert config.slippage > 0
        assert config.commission < 1.0  # 100% 미만
        assert config.slippage < 1.0    # 100% 미만

    def test_backtest_config_immutability(self):
        """BacktestConfig는 dataclass이므로 속성 변경 가능 확인"""
        config = BacktestConfig()

        # dataclass는 기본적으로 mutable
        config.min_return = 15.0
        assert config.min_return == 15.0

    def test_backtest_config_repr(self):
        """BacktestConfig의 repr 메서드 테스트"""
        config = BacktestConfig(days=365, min_return=10.0)

        # dataclass는 자동으로 repr 생성
        repr_str = repr(config)
        assert "BacktestConfig" in repr_str
        assert "days=365" in repr_str
        assert "min_return=10.0" in repr_str
