"""
Phase 1: Research Pass Config 테스트

TDD RED Phase - 테스트 먼저 작성
목표: 느슨한 필터 설정으로 후보 생성 확인
"""
import pytest
from typing import Dict, Any

# 아직 구현되지 않은 클래스/함수 - 테스트가 실패해야 함
from src.backtesting.quick_filter import (
    QuickBacktestFilter,
    QuickBacktestConfig,
    ResearchPassConfig,  # 새로 추가할 클래스
    TradingPassConfig,   # 새로 추가할 클래스
    PassResult,          # 새로 추가할 클래스
)


class TestResearchPassConfig:
    """ResearchPassConfig 기본값 테스트"""

    def test_research_pass_config_exists(self):
        """ResearchPassConfig 클래스가 존재하는지 확인"""
        config = ResearchPassConfig()
        assert config is not None

    def test_research_pass_config_has_loose_thresholds(self):
        """Research Pass는 느슨한 임계값을 가져야 함"""
        config = ResearchPassConfig()

        # 계획 문서 기준 임계값
        assert config.min_return == 8.0  # 현재 15% → 8%
        assert config.min_win_rate == 30.0  # 현재 38% → 30%
        assert config.min_profit_factor == 1.3  # 현재 1.8 → 1.3
        assert config.min_sharpe_ratio == 0.4  # 현재 1.0 → 0.4
        assert config.max_drawdown == 30.0  # 현재 15% → 30%
        assert config.min_trades == 20  # 동일

    def test_research_pass_is_looser_than_current(self):
        """Research Pass 임계값이 현재 QuickBacktestConfig보다 느슨한지 확인"""
        research = ResearchPassConfig()
        current = QuickBacktestConfig()

        # minimum 필터: Research가 더 낮아야 함
        assert research.min_return < current.min_return
        assert research.min_win_rate < current.min_win_rate
        assert research.min_profit_factor < current.min_profit_factor
        assert research.min_sharpe_ratio < current.min_sharpe_ratio

        # maximum 필터: Research가 더 높아야 함 (더 관대)
        assert research.max_drawdown > current.max_drawdown


class TestTradingPassConfig:
    """TradingPassConfig 기본값 테스트"""

    def test_trading_pass_config_exists(self):
        """TradingPassConfig 클래스가 존재하는지 확인"""
        config = TradingPassConfig()
        assert config is not None

    def test_trading_pass_config_has_moderate_thresholds(self):
        """Trading Pass는 중간 수준의 임계값을 가져야 함"""
        config = TradingPassConfig()

        # 계획 문서 기준 임계값
        assert config.min_return == 12.0
        assert config.min_win_rate == 35.0
        assert config.min_profit_factor == 1.5
        assert config.min_sharpe_ratio == 0.7
        assert config.max_drawdown == 25.0
        # min_trades: 50 → 25로 조정 (2026-01-03)
        # 근거: 상위 20개 코인 분석 결과, 최대 28회 거래 (BTC, 일봉 2년 기준)
        # 50회 기준: 0/16 코인 통과 (0%) - 비현실적
        assert config.min_trades == 25

    def test_trading_pass_is_stricter_than_research(self):
        """Trading Pass가 Research Pass보다 엄격한지 확인"""
        research = ResearchPassConfig()
        trading = TradingPassConfig()

        # minimum 필터: Trading이 더 높아야 함
        assert trading.min_return > research.min_return
        assert trading.min_win_rate > research.min_win_rate
        assert trading.min_profit_factor > research.min_profit_factor
        assert trading.min_sharpe_ratio > research.min_sharpe_ratio
        assert trading.min_trades > research.min_trades

        # maximum 필터: Trading이 더 낮아야 함 (더 엄격)
        assert trading.max_drawdown < research.max_drawdown


class TestPassResult:
    """PassResult 데이터클래스 테스트"""

    def test_pass_result_structure(self):
        """PassResult가 올바른 구조를 가지는지 확인"""
        result = PassResult(
            passed=True,
            pass_type='research',
            passed_count=8,
            failed_count=4,
            failed_filters=['sharpe_ratio', 'profit_factor'],
            reason="8/12 필터 통과"
        )

        assert result.passed is True
        assert result.pass_type == 'research'
        assert result.passed_count == 8
        assert result.failed_count == 4
        assert 'sharpe_ratio' in result.failed_filters
        assert '8/12' in result.reason


class TestResearchPassEvaluation:
    """Research Pass 평가 테스트"""

    @pytest.fixture
    def sample_metrics_moderate(self) -> Dict[str, Any]:
        """중간 수준의 메트릭 (Research 통과, Trading 미달)"""
        return {
            'total_return': 10.0,  # Research 8% 통과, Trading 12% 미달
            'win_rate': 32.0,  # Research 30% 통과, Trading 35% 미달
            'profit_factor': 1.4,  # Research 1.3 통과, Trading 1.5 미달
            'sharpe_ratio': 0.5,  # Research 0.4 통과, Trading 0.7 미달
            'sortino_ratio': 0.8,
            'calmar_ratio': 0.3,
            'max_drawdown': -25.0,  # Research 30% 통과, Trading 25% 경계
            'max_consecutive_losses': 4,
            'volatility': 60.0,
            'total_trades': 30,  # Research 20 통과, Trading 25 통과
            'avg_win': 4.0,
            'avg_loss': -3.0,
            'avg_holding_period_hours': 72.0,
        }

    @pytest.fixture
    def sample_metrics_poor(self) -> Dict[str, Any]:
        """낮은 수준의 메트릭 (Research도 미달)"""
        return {
            'total_return': 5.0,  # Research 8% 미달
            'win_rate': 25.0,  # Research 30% 미달
            'profit_factor': 1.1,  # Research 1.3 미달
            'sharpe_ratio': 0.2,  # Research 0.4 미달
            'sortino_ratio': 0.4,
            'calmar_ratio': 0.2,
            'max_drawdown': -35.0,  # Research 30% 미달
            'max_consecutive_losses': 6,
            'volatility': 80.0,
            'total_trades': 15,  # Research 20 미달
            'avg_win': 2.0,
            'avg_loss': -2.5,
            'avg_holding_period_hours': 120.0,
        }

    def test_evaluate_research_pass_with_moderate_metrics(self, sample_metrics_moderate):
        """중간 수준 메트릭으로 Research Pass 평가"""
        config = ResearchPassConfig()
        filter_obj = QuickBacktestFilter(config)

        # 새로운 메서드: evaluate_research_pass
        result = filter_obj.evaluate_research_pass(sample_metrics_moderate)

        assert isinstance(result, PassResult)
        assert result.pass_type == 'research'
        # 핵심 필터들은 통과해야 함
        assert result.passed is True

    def test_evaluate_research_pass_with_poor_metrics(self, sample_metrics_poor):
        """낮은 수준 메트릭은 Research Pass도 실패"""
        config = ResearchPassConfig()
        filter_obj = QuickBacktestFilter(config)

        result = filter_obj.evaluate_research_pass(sample_metrics_poor)

        assert result.passed is False
        assert len(result.failed_filters) > 0

    def test_evaluate_trading_pass_with_moderate_metrics(self, sample_metrics_moderate):
        """중간 수준 메트릭으로 Trading Pass 평가 (실패 예상)"""
        config = TradingPassConfig()
        filter_obj = QuickBacktestFilter(config)

        # 새로운 메서드: evaluate_trading_pass
        result = filter_obj.evaluate_trading_pass(sample_metrics_moderate)

        assert isinstance(result, PassResult)
        assert result.pass_type == 'trading'
        # Trading Pass는 더 엄격하므로 실패해야 함
        assert result.passed is False


class TestTwoGateArchitecture:
    """2단 게이트 아키텍처 테스트"""

    @pytest.fixture
    def sample_metrics_good(self) -> Dict[str, Any]:
        """좋은 수준의 메트릭 (Research, Trading 모두 통과)"""
        return {
            'total_return': 20.0,
            'win_rate': 45.0,
            'profit_factor': 2.0,
            'sharpe_ratio': 1.2,
            'sortino_ratio': 1.5,
            'calmar_ratio': 1.0,
            'max_drawdown': -12.0,
            'max_consecutive_losses': 3,
            'volatility': 40.0,
            'total_trades': 60,
            'avg_win': 5.0,
            'avg_loss': -2.5,
            'avg_holding_period_hours': 48.0,
        }

    def test_research_and_trading_pass_both_succeed(self, sample_metrics_good):
        """좋은 메트릭은 Research, Trading 모두 통과"""
        research_config = ResearchPassConfig()
        trading_config = TradingPassConfig()

        filter_research = QuickBacktestFilter(research_config)
        filter_trading = QuickBacktestFilter(trading_config)

        research_result = filter_research.evaluate_research_pass(sample_metrics_good)
        trading_result = filter_trading.evaluate_trading_pass(sample_metrics_good)

        assert research_result.passed is True
        assert trading_result.passed is True

    def test_factory_methods_exist(self):
        """팩토리 메서드로 Config 생성 가능"""
        # 팩토리 메서드 테스트
        research_config = QuickBacktestConfig.create_research_config()
        trading_config = QuickBacktestConfig.create_trading_config()

        assert research_config is not None
        assert trading_config is not None

        # 타입 확인
        assert isinstance(research_config, (QuickBacktestConfig, ResearchPassConfig))
        assert isinstance(trading_config, (QuickBacktestConfig, TradingPassConfig))


class TestConfigComparison:
    """Config 비교 테스트 - 3단계 필터 강도 검증"""

    def test_three_tier_filter_strength(self):
        """
        필터 강도: Research < Trading < Current(Original)

        Current는 기존 QuickBacktestConfig (가장 엄격)
        """
        research = ResearchPassConfig()
        trading = TradingPassConfig()
        current = QuickBacktestConfig()

        # Sharpe Ratio 순서: 0.4 < 0.7 < 1.0
        assert research.min_sharpe_ratio < trading.min_sharpe_ratio < current.min_sharpe_ratio

        # Profit Factor 순서: 1.3 < 1.5 < 1.8
        assert research.min_profit_factor < trading.min_profit_factor < current.min_profit_factor

        # Max Drawdown 순서 (허용치): 30 > 25 > 15
        assert research.max_drawdown > trading.max_drawdown > current.max_drawdown
