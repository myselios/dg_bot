"""
MultiCoinBacktest 단위 테스트
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime
import pandas as pd
import numpy as np

from src.scanner.multi_backtest import (
    MultiCoinBacktest,
    MultiBacktestConfig,
    BacktestScore
)
from src.scanner.liquidity_scanner import CoinInfo


class TestMultiBacktestConfig:
    """MultiBacktestConfig 데이터클래스 테스트"""

    def test_default_config(self):
        """기본 설정값 테스트 - Research Pass 기준 (느슨한 기준)"""
        config = MultiBacktestConfig()

        # 수익성 지표 (Research Pass 기준)
        assert config.min_return == 8.0
        assert config.min_win_rate == 30.0
        assert config.min_profit_factor == 1.3

        # 위험조정 수익률 (Research Pass 기준)
        assert config.min_sharpe_ratio == 0.4
        assert config.min_sortino_ratio == 0.5
        assert config.min_calmar_ratio == 0.25

        # 리스크 관리 (Research Pass 기준)
        assert config.max_drawdown == 30.0
        assert config.max_consecutive_losses == 8
        assert config.max_volatility == 100.0

        # 통계적 유의성
        assert config.min_trades == 20

        # 거래 품질 (Research Pass 기준)
        assert config.min_avg_win_loss_ratio == 1.0
        assert config.max_avg_holding_hours == 336.0

    def test_custom_config(self):
        """커스텀 설정값 테스트"""
        config = MultiBacktestConfig(
            min_return=20.0,
            min_win_rate=45.0,
            min_sharpe_ratio=1.5,
            max_drawdown=10.0
        )

        assert config.min_return == 20.0
        assert config.min_win_rate == 45.0
        assert config.min_sharpe_ratio == 1.5
        assert config.max_drawdown == 10.0

    def test_weight_sum(self):
        """가중치 합계 확인 (약 1.0)"""
        config = MultiBacktestConfig()

        total_weight = (
            config.weight_return +
            config.weight_win_rate +
            config.weight_profit_factor +
            config.weight_sharpe +
            config.weight_drawdown +
            config.weight_sortino
        )

        assert 0.99 <= total_weight <= 1.01


class TestBacktestScore:
    """BacktestScore 데이터클래스 테스트"""

    def test_backtest_score_creation(self):
        """BacktestScore 객체 생성 테스트"""
        score = BacktestScore(
            ticker="KRW-BTC",
            symbol="BTC",
            passed=True,
            score=85.5,
            grade="STRONG PASS",
            metrics={'total_return': 25.0, 'win_rate': 45.0},
            filter_results={'return': True, 'win_rate': True},
            reason="모든 조건 충족"
        )

        assert score.ticker == "KRW-BTC"
        assert score.symbol == "BTC"
        assert score.score == 85.5
        assert score.grade == "STRONG PASS"
        assert score.passed is True

    def test_backtest_score_failed(self):
        """실패한 BacktestScore 테스트"""
        score = BacktestScore(
            ticker="KRW-XRP",
            symbol="XRP",
            passed=False,
            score=30.0,
            grade="FAIL",
            metrics={'total_return': 5.0, 'win_rate': 30.0},
            filter_results={'return': False, 'win_rate': False},
            reason="수익률 미달"
        )

        assert score.passed is False
        assert score.grade == "FAIL"


class TestMultiCoinBacktest:
    """MultiCoinBacktest 클래스 테스트"""

    def test_initialization(self):
        """초기화 테스트"""
        backtest = MultiCoinBacktest()

        assert backtest.config is not None
        assert backtest.data_sync is not None
        assert backtest.max_workers >= 1

    def test_custom_config(self):
        """커스텀 설정으로 초기화"""
        config = MultiBacktestConfig(min_return=25.0)
        backtest = MultiCoinBacktest(config=config)

        assert backtest.config.min_return == 25.0

    def test_get_filter_criteria_default(self):
        """기본 필터 기준 반환 테스트 - Research Pass 기준"""
        backtest = MultiCoinBacktest()
        criteria = backtest._get_filter_criteria(None)

        # Research Pass 기준 (느슨한 기준)
        assert criteria['min_return'] == 8.0
        assert criteria['min_win_rate'] == 30.0
        assert criteria['min_sharpe_ratio'] == 0.4
        assert criteria['max_drawdown'] == 30.0
        assert criteria['min_trades'] == 20

    def test_get_filter_criteria_custom(self):
        """커스텀 필터 기준 반환 테스트"""
        backtest = MultiCoinBacktest()
        custom = {'min_return': 30.0, 'min_win_rate': 50.0}
        criteria = backtest._get_filter_criteria(custom)

        assert criteria == custom

    def test_check_filters_all_pass(self):
        """모든 필터 통과 테스트"""
        backtest = MultiCoinBacktest()

        metrics = {
            'total_return': 20.0,
            'win_rate': 45.0,
            'profit_factor': 2.0,
            'sharpe_ratio': 1.5,
            'sortino_ratio': 1.8,
            'calmar_ratio': 1.2,
            'max_drawdown': -10.0,
            'max_consecutive_losses': 3,
            'volatility': 30.0,
            'total_trades': 30,
            'avg_win': 5.0,
            'avg_loss': -3.0,
            'avg_holding_period_hours': 48.0
        }

        criteria = backtest._get_filter_criteria(None)
        results = backtest._check_filters(metrics, criteria)

        # 모든 필터가 True여야 함
        assert all(results.values())

    def test_check_filters_some_fail(self):
        """일부 필터 실패 테스트 - Research Pass 기준"""
        backtest = MultiCoinBacktest()

        metrics = {
            'total_return': 5.0,  # 8% 미만 - 실패
            'win_rate': 25.0,     # 30% 미만 - 실패
            'profit_factor': 2.0,
            'sharpe_ratio': 1.5,
            'sortino_ratio': 1.8,
            'calmar_ratio': 1.2,
            'max_drawdown': -10.0,
            'max_consecutive_losses': 3,
            'volatility': 30.0,
            'total_trades': 30,
            'avg_win': 5.0,
            'avg_loss': -3.0,
            'avg_holding_period_hours': 48.0
        }

        criteria = backtest._get_filter_criteria(None)
        results = backtest._check_filters(metrics, criteria)

        assert results['return'] is False   # 5.0 < 8.0 (Research 기준)
        assert results['win_rate'] is False  # 25.0 < 30.0 (Research 기준)
        assert results['sharpe_ratio'] is True

    def test_check_filters_drawdown(self):
        """MDD 필터 테스트 - Research Pass 기준 (max_drawdown=30%)"""
        backtest = MultiCoinBacktest()

        metrics = {
            'total_return': 20.0,
            'win_rate': 45.0,
            'profit_factor': 2.0,
            'sharpe_ratio': 1.5,
            'sortino_ratio': 1.8,
            'calmar_ratio': 1.2,
            'max_drawdown': -35.0,  # 30% 초과 - 실패 (Research 기준)
            'max_consecutive_losses': 3,
            'volatility': 30.0,
            'total_trades': 30,
            'avg_win': 5.0,
            'avg_loss': -3.0,
            'avg_holding_period_hours': 48.0
        }

        criteria = backtest._get_filter_criteria(None)
        results = backtest._check_filters(metrics, criteria)

        assert results['max_drawdown'] is False  # -35% > 30% limit

    def test_calculate_score_high(self):
        """높은 점수 계산 테스트"""
        backtest = MultiCoinBacktest()

        metrics = {
            'total_return': 30.0,      # 높은 수익률
            'win_rate': 55.0,          # 높은 승률
            'profit_factor': 2.5,      # 높은 손익비
            'sharpe_ratio': 1.8,       # 높은 샤프
            'sortino_ratio': 2.2,      # 높은 소르티노
            'max_drawdown': -5.0       # 낮은 MDD
        }

        score = backtest._calculate_score(metrics)

        # 점수는 70점 이상이어야 함
        assert score >= 70

    def test_calculate_score_low(self):
        """낮은 점수 계산 테스트"""
        backtest = MultiCoinBacktest()

        metrics = {
            'total_return': 5.0,       # 낮은 수익률
            'win_rate': 35.0,          # 낮은 승률
            'profit_factor': 1.1,      # 낮은 손익비
            'sharpe_ratio': 0.3,       # 낮은 샤프
            'sortino_ratio': 0.4,      # 낮은 소르티노
            'max_drawdown': -20.0      # 높은 MDD
        }

        score = backtest._calculate_score(metrics)

        # 점수는 50점 이하여야 함
        assert score <= 50

    def test_determine_grade_strong_pass(self):
        """STRONG PASS 등급 테스트"""
        backtest = MultiCoinBacktest()

        grade = backtest._determine_grade(85.0, passed=True)
        assert grade == "STRONG PASS"

    def test_determine_grade_weak_pass(self):
        """WEAK PASS 등급 테스트"""
        backtest = MultiCoinBacktest()

        grade = backtest._determine_grade(65.0, passed=True)
        assert grade == "WEAK PASS"

    def test_determine_grade_fail(self):
        """FAIL 등급 테스트"""
        backtest = MultiCoinBacktest()

        grade = backtest._determine_grade(50.0, passed=False)
        assert grade == "FAIL"

    def test_generate_reason_passed(self):
        """성공 사유 생성 테스트"""
        backtest = MultiCoinBacktest()

        metrics = {'total_return': 25.0, 'profit_factor': 2.0}
        filter_results = {'return': True, 'win_rate': True}

        reason = backtest._generate_reason(metrics, filter_results, passed=True)

        assert "수익률" in reason
        assert "25.0%" in reason

    def test_generate_reason_failed(self):
        """실패 사유 생성 테스트"""
        backtest = MultiCoinBacktest()

        metrics = {'total_return': 5.0, 'win_rate': 30.0, 'profit_factor': 1.0}
        filter_results = {'return': False, 'win_rate': False}

        reason = backtest._generate_reason(metrics, filter_results, passed=False)

        assert "수익률" in reason or "미달" in reason


@pytest.mark.asyncio
class TestMultiCoinBacktestAsync:
    """MultiCoinBacktest 비동기 메서드 테스트"""

    @pytest.fixture
    def sample_ohlcv_data(self):
        """샘플 OHLCV 데이터"""
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        return pd.DataFrame({
            'open': [100 + i * 0.5 for i in range(100)],
            'high': [105 + i * 0.5 for i in range(100)],
            'low': [95 + i * 0.5 for i in range(100)],
            'close': [102 + i * 0.5 for i in range(100)],
            'volume': [1000 + i * 10 for i in range(100)]
        }, index=dates)

    @pytest.fixture
    def sample_coin_infos(self):
        """샘플 코인 정보"""
        return {
            'KRW-BTC': CoinInfo(
                ticker='KRW-BTC',
                symbol='BTC',
                korean_name='비트코인',
                current_price=50000000,
                volume_24h=1000,
                acc_trade_price_24h=100_000_000_000,
                signed_change_rate=2.0,
                high_price=51000000,
                low_price=49000000
            ),
            'KRW-ETH': CoinInfo(
                ticker='KRW-ETH',
                symbol='ETH',
                korean_name='이더리움',
                current_price=4000000,
                volume_24h=5000,
                acc_trade_price_24h=50_000_000_000,
                signed_change_rate=1.5,
                high_price=4100000,
                low_price=3900000
            )
        }

    async def test_run_parallel_backtest_empty_list(self):
        """빈 코인 목록 처리"""
        backtest = MultiCoinBacktest()

        result = await backtest.run_parallel_backtest(coin_list=[])

        assert result == []

    async def test_run_parallel_backtest_no_data(self):
        """데이터 없는 경우 처리"""
        backtest = MultiCoinBacktest()

        with patch.object(backtest.data_sync, 'load_data', return_value=None):
            result = await backtest.run_parallel_backtest(
                coin_list=['KRW-BTC', 'KRW-ETH'],
                top_n=5
            )

            # 데이터 없으면 FAIL 결과 반환
            assert isinstance(result, list)
            for r in result:
                assert r.passed is False

    async def test_run_parallel_backtest_with_data(self, sample_ohlcv_data, sample_coin_infos):
        """데이터 있는 경우 백테스팅 실행"""
        backtest = MultiCoinBacktest()

        # 좋은 결과 메트릭 모킹
        mock_result = MagicMock()
        mock_result.metrics = {
            'total_return': 25.0,
            'win_rate': 50.0,
            'profit_factor': 2.2,
            'sharpe_ratio': 1.5,
            'sortino_ratio': 1.8,
            'calmar_ratio': 1.2,
            'max_drawdown': -8.0,
            'max_consecutive_losses': 3,
            'volatility': 25.0,
            'total_trades': 40,
            'avg_win': 5.0,
            'avg_loss': -2.5,
            'avg_holding_period_hours': 72.0
        }

        with patch.object(backtest.data_sync, 'load_data', return_value=sample_ohlcv_data):
            with patch.object(backtest, '_execute_backtest', return_value=mock_result):
                result = await backtest.run_parallel_backtest(
                    coin_list=['KRW-BTC'],
                    coin_infos=sample_coin_infos,
                    top_n=1
                )

                assert len(result) == 1
                assert result[0].ticker == 'KRW-BTC'
