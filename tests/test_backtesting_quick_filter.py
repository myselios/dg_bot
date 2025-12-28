"""
빠른 백테스팅 필터링 테스트
TDD 원칙에 따라 테스트를 먼저 작성합니다.
"""
import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from src.backtesting.quick_filter import (
    QuickBacktestFilter,
    QuickBacktestConfig,
    QuickBacktestResult
)
from src.backtesting.backtester import BacktestResult


@pytest.fixture
def sample_30day_data():
    """30일 샘플 데이터"""
    dates = pd.date_range('2024-01-01', periods=30, freq='D')
    return {
        'day': pd.DataFrame({
            'open': [100 + i * 0.5 for i in range(30)],
            'high': [105 + i * 0.5 for i in range(30)],
            'low': [95 + i * 0.5 for i in range(30)],
            'close': [102 + i * 0.5 for i in range(30)],
            'volume': [1000 + i * 10 for i in range(30)]
        }, index=dates),
        'minute60': pd.DataFrame(),
        'minute15': pd.DataFrame()
    }


@pytest.fixture
def sample_multi_timeframe_data():
    """일봉, 시봉, 분봉 샘플 데이터"""
    daily_dates = pd.date_range('2024-01-01', periods=30, freq='D')
    hourly_dates = pd.date_range('2024-01-01', periods=720, freq='H')  # 30일 * 24시간
    minute_dates = pd.date_range('2024-01-01', periods=2880, freq='15min')  # 30일 * 96 (15분봉)
    
    return {
        'day': pd.DataFrame({
            'open': [100 + i * 0.5 for i in range(30)],
            'high': [105 + i * 0.5 for i in range(30)],
            'low': [95 + i * 0.5 for i in range(30)],
            'close': [102 + i * 0.5 for i in range(30)],
            'volume': [1000 + i * 10 for i in range(30)]
        }, index=daily_dates),
        'minute60': pd.DataFrame({
            'open': [100 + i * 0.02 for i in range(720)],
            'high': [105 + i * 0.02 for i in range(720)],
            'low': [95 + i * 0.02 for i in range(720)],
            'close': [102 + i * 0.02 for i in range(720)],
            'volume': [100 + i for i in range(720)]
        }, index=hourly_dates),
        'minute15': pd.DataFrame({
            'open': [100 + i * 0.005 for i in range(2880)],
            'high': [105 + i * 0.005 for i in range(2880)],
            'low': [95 + i * 0.005 for i in range(2880)],
            'close': [102 + i * 0.005 for i in range(2880)],
            'volume': [50 + i * 0.1 for i in range(2880)]
        }, index=minute_dates)
    }


@pytest.fixture
def mock_backtest_result_passed():
    """필터링 통과 Mock 백테스트 결과"""
    return BacktestResult(
        initial_capital=10_000_000,
        final_equity=11_000_000,
        equity_curve=[10_000_000 + i * 33333 for i in range(30)],
        trades=[],
        metrics={
            'total_return': 10.0,      # 10% 수익률 (5% 초과)
            'win_rate': 60.0,          # 60% 승률 (50% 초과)
            'sharpe_ratio': 1.5,       # 1.5 (1.0 초과)
            'max_drawdown': -10.0,     # -10% (15% 미만)
            'total_trades': 10,
            'profit_factor': 1.8,
            'final_equity': 11_000_000,
            'volatility': 20.0,
            'sortino_ratio': 1.2,
            'calmar_ratio': 1.0,
            'winning_trades': 6,
            'losing_trades': 4,
            'avg_win': 200_000,
            'avg_loss': -100_000,
            'max_consecutive_wins': 4,
            'max_consecutive_losses': 2,
            'avg_holding_period_hours': 48.0,
            'total_commission': 50_000
        }
    )


@pytest.fixture
def mock_backtest_result_failed():
    """필터링 미달 Mock 백테스트 결과"""
    return BacktestResult(
        initial_capital=10_000_000,
        final_equity=10_300_000,
        equity_curve=[10_000_000 + i * 10000 for i in range(30)],
        trades=[],
        metrics={
            'total_return': 3.0,       # 3% 수익률 (5% 미만)
            'win_rate': 45.0,          # 45% 승률 (50% 미만)
            'sharpe_ratio': 0.5,       # 0.5 (1.0 미만)
            'max_drawdown': -20.0,     # -20% (15% 초과)
            'total_trades': 10,
            'profit_factor': 0.8,
            'final_equity': 10_300_000,
            'volatility': 25.0,
            'sortino_ratio': 0.3,
            'calmar_ratio': 0.15,
            'winning_trades': 4,
            'losing_trades': 6,
            'avg_win': 150_000,
            'avg_loss': -200_000,
            'max_consecutive_wins': 2,
            'max_consecutive_losses': 4,
            'avg_holding_period_hours': 72.0,
            'total_commission': 50_000
        }
    )


class TestQuickBacktestConfig:
    """QuickBacktestConfig 테스트"""
    
    @pytest.mark.unit
    def test_default_config(self):
        """기본 설정 테스트"""
        # When
        config = QuickBacktestConfig()
        
        # Then
        assert config.days == 730  # 변경됨: 365 -> 730 (2년)
        assert config.use_local_data == True  # 새로 추가됨
        assert config.initial_capital == 10_000_000
        assert config.commission == 0.0005
        assert config.slippage == 0.0001
        assert config.min_return == 3.0
        assert config.min_win_rate == 35.0
        assert config.min_sharpe_ratio == 0.8
        assert config.max_drawdown == 20.0
    
    @pytest.mark.unit
    def test_custom_config(self):
        """커스텀 설정 테스트"""
        # When
        config = QuickBacktestConfig(
            days=60,
            min_return=10.0,
            min_win_rate=60.0,
            min_sharpe_ratio=1.5,
            max_drawdown=10.0
        )
        
        # Then
        assert config.days == 60
        assert config.min_return == 10.0
        assert config.min_win_rate == 60.0
        assert config.min_sharpe_ratio == 1.5
        assert config.max_drawdown == 10.0


class TestQuickBacktestFilter:
    """QuickBacktestFilter 클래스 테스트"""
    
    @pytest.mark.unit
    def test_filter_initialization(self):
        """필터 초기화 테스트"""
        # When
        filter_instance = QuickBacktestFilter()
        
        # Then
        assert filter_instance.config is not None
        assert isinstance(filter_instance.config, QuickBacktestConfig)
        assert filter_instance.data_provider is not None
    
    @pytest.mark.unit
    def test_filter_initialization_with_custom_config(self):
        """커스텀 설정으로 필터 초기화 테스트"""
        # Given
        config = QuickBacktestConfig(min_return=10.0)
        
        # When
        filter_instance = QuickBacktestFilter(config)
        
        # Then
        assert filter_instance.config.min_return == 10.0
    
    @pytest.mark.unit
    @patch('src.backtesting.quick_filter.BacktestRunner')
    def test_run_quick_backtest_passed(
        self,
        mock_runner_class,
        sample_30day_data,
        mock_backtest_result_passed
    ):
        """필터링 조건 통과 테스트 (일봉만)"""
        # Given
        ticker = 'KRW-ETH'
        mock_runner = Mock()
        mock_runner.run_backtest.return_value = mock_backtest_result_passed
        mock_runner_class.run_backtest = Mock(return_value=mock_backtest_result_passed)
        
        config = QuickBacktestConfig(use_local_data=False, days=30)
        filter_instance = QuickBacktestFilter(config)
        
        # When
        result = filter_instance.run_quick_backtest(ticker, sample_30day_data)
        
        # Then
        assert isinstance(result, QuickBacktestResult)
        assert result.passed is True
        assert result.result is not None
        assert 'total_return' in result.metrics
        assert result.metrics['total_return'] == 10.0
        assert all(result.filter_results.values())  # 모든 조건 통과
        assert "통과" in result.reason or "모든" in result.reason
    
    @pytest.mark.unit
    @patch('src.backtesting.quick_filter.BacktestRunner')
    def test_run_quick_backtest_failed(
        self,
        mock_runner_class,
        sample_30day_data,
        mock_backtest_result_failed
    ):
        """필터링 조건 미달 테스트 (일봉만)"""
        # Given
        ticker = 'KRW-ETH'
        mock_runner_class.run_backtest = Mock(return_value=mock_backtest_result_failed)
        
        config = QuickBacktestConfig(use_local_data=False, days=30)
        filter_instance = QuickBacktestFilter(config)
        
        # When
        result = filter_instance.run_quick_backtest(ticker, sample_30day_data)
        
        # Then
        assert isinstance(result, QuickBacktestResult)
        assert result.passed is False
        assert result.result is not None
        assert not all(result.filter_results.values())  # 일부 조건 미달
        assert "미달" in result.reason or "실패" in result.reason
    
    @pytest.mark.unit
    @patch('src.backtesting.quick_filter.HistoricalDataProvider')
    def test_run_quick_backtest_empty_data(self, mock_data_provider_class):
        """빈 데이터 테스트"""
        # Given
        ticker = 'KRW-ETH'
        empty_data = {
            'day': pd.DataFrame(),
            'minute60': pd.DataFrame(),
            'minute15': pd.DataFrame()
        }
        config = QuickBacktestConfig(use_local_data=False, days=30)
        filter_instance = QuickBacktestFilter(config)
        
        # When
        result = filter_instance.run_quick_backtest(ticker, empty_data)
        
        # Then
        assert isinstance(result, QuickBacktestResult)
        assert result.passed is False
        assert result.result is None
        assert "없습니다" in result.reason or "부족" in result.reason
    
    @pytest.mark.unit
    @patch('src.backtesting.quick_filter.HistoricalDataProvider')
    def test_run_quick_backtest_insufficient_data(self, mock_data_provider_class):
        """데이터 부족 테스트 (10개 미만)"""
        # Given
        ticker = 'KRW-ETH'
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        insufficient_data = {
            'day': pd.DataFrame({
                'open': [100 + i for i in range(5)],
                'high': [105 + i for i in range(5)],
                'low': [95 + i for i in range(5)],
                'close': [102 + i for i in range(5)],
                'volume': [1000 + i * 10 for i in range(5)]
            }, index=dates),
            'minute60': pd.DataFrame(),
            'minute15': pd.DataFrame()
        }
        config = QuickBacktestConfig(use_local_data=False, days=30)
        filter_instance = QuickBacktestFilter(config)
        
        # When
        result = filter_instance.run_quick_backtest(ticker, insufficient_data)
        
        # Then
        assert isinstance(result, QuickBacktestResult)
        assert result.passed is False
        assert result.result is None
        assert "부족" in result.reason or "10개" in result.reason
    
    @pytest.mark.unit
    def test_check_filters_all_passed(self):
        """모든 필터 조건 통과 테스트"""
        # Given
        filter_instance = QuickBacktestFilter()
        metrics = {
            'total_return': 10.0,
            'win_rate': 60.0,
            'sharpe_ratio': 1.5,
            'max_drawdown': -10.0
        }
        
        # When
        filter_results = filter_instance._check_filters(metrics)
        
        # Then
        assert filter_results['return'] is True
        assert filter_results['win_rate'] is True
        assert filter_results['sharpe_ratio'] is True
        assert filter_results['max_drawdown'] is True
    
    @pytest.mark.unit
    def test_check_filters_failed_return(self):
        """수익률 필터 실패 테스트"""
        # Given
        filter_instance = QuickBacktestFilter()
        metrics = {
            'total_return': 2.0,  # 3% 미만
            'win_rate': 60.0,
            'sharpe_ratio': 1.5,
            'max_drawdown': -10.0
        }
        
        # When
        filter_results = filter_instance._check_filters(metrics)
        
        # Then
        assert filter_results['return'] is False
        assert filter_results['win_rate'] is True
        assert filter_results['sharpe_ratio'] is True
        assert filter_results['max_drawdown'] is True
    
    @pytest.mark.unit
    def test_check_filters_failed_win_rate(self):
        """승률 필터 실패 테스트"""
        # Given
        filter_instance = QuickBacktestFilter()
        metrics = {
            'total_return': 10.0,
            'win_rate': 30.0,  # 35% 미만
            'sharpe_ratio': 1.5,
            'max_drawdown': -10.0
        }
        
        # When
        filter_results = filter_instance._check_filters(metrics)
        
        # Then
        assert filter_results['return'] is True
        assert filter_results['win_rate'] is False
        assert filter_results['sharpe_ratio'] is True
        assert filter_results['max_drawdown'] is True
    
    @pytest.mark.unit
    def test_check_filters_failed_sharpe(self):
        """Sharpe Ratio 필터 실패 테스트"""
        # Given
        filter_instance = QuickBacktestFilter()
        metrics = {
            'total_return': 10.0,
            'win_rate': 60.0,
            'sharpe_ratio': 0.5,  # 1.0 미만
            'max_drawdown': -10.0
        }
        
        # When
        filter_results = filter_instance._check_filters(metrics)
        
        # Then
        assert filter_results['return'] is True
        assert filter_results['win_rate'] is True
        assert filter_results['sharpe_ratio'] is False
        assert filter_results['max_drawdown'] is True
    
    @pytest.mark.unit
    def test_check_filters_failed_drawdown(self):
        """Max Drawdown 필터 실패 테스트"""
        # Given
        filter_instance = QuickBacktestFilter()
        metrics = {
            'total_return': 10.0,
            'win_rate': 60.0,
            'sharpe_ratio': 1.5,
            'max_drawdown': -25.0  # -25% (20% 초과)
        }
        
        # When
        filter_results = filter_instance._check_filters(metrics)
        
        # Then
        assert filter_results['return'] is True
        assert filter_results['win_rate'] is True
        assert filter_results['sharpe_ratio'] is True
        assert filter_results['max_drawdown'] is False
    
    @pytest.mark.unit
    def test_check_filters_boundary_values(self):
        """경계값 테스트 (정확히 경계값인 경우)"""
        # Given
        filter_instance = QuickBacktestFilter()
        metrics = {
            'total_return': 3.0,      # 정확히 3%
            'win_rate': 35.0,         # 정확히 35%
            'sharpe_ratio': 0.8,      # 정확히 0.8
            'max_drawdown': -20.0     # 정확히 -20%
        }
        
        # When
        filter_results = filter_instance._check_filters(metrics)
        
        # Then (경계값 포함이므로 모두 True)
        assert filter_results['return'] is True
        assert filter_results['win_rate'] is True
        assert filter_results['sharpe_ratio'] is True
        assert filter_results['max_drawdown'] is True
    
    @pytest.mark.unit
    def test_generate_reason_passed(self):
        """통과 사유 생성 테스트"""
        # Given
        filter_instance = QuickBacktestFilter()
        metrics = {
            'total_return': 10.0,
            'win_rate': 60.0,
            'sharpe_ratio': 1.5,
            'max_drawdown': -10.0
        }
        filter_results = {
            'return': True,
            'win_rate': True,
            'sharpe_ratio': True,
            'max_drawdown': True
        }
        
        # When
        reason = filter_instance._generate_reason(metrics, filter_results, True)
        
        # Then
        assert "통과" in reason or "모든" in reason
    
    @pytest.mark.unit
    def test_generate_reason_failed(self):
        """실패 사유 생성 테스트"""
        # Given
        filter_instance = QuickBacktestFilter()
        metrics = {
            'total_return': 3.0,
            'win_rate': 45.0,
            'sharpe_ratio': 0.5,
            'max_drawdown': -20.0
        }
        filter_results = {
            'return': False,
            'win_rate': False,
            'sharpe_ratio': False,
            'max_drawdown': False
        }
        
        # When
        reason = filter_instance._generate_reason(metrics, filter_results, False)
        
        # Then
        assert "미달" in reason or "실패" in reason
        assert "수익률" in reason or "3.0" in reason


class TestQuickBacktestResult:
    """QuickBacktestResult 데이터 클래스 테스트"""
    
    @pytest.mark.unit
    def test_result_creation(self):
        """결과 객체 생성 테스트"""
        # Given
        passed = True
        result = Mock()
        metrics = {'total_return': 10.0}
        filter_results = {'return': True}
        reason = "통과"
        
        # When
        quick_result = QuickBacktestResult(
            passed=passed,
            result=result,
            metrics=metrics,
            filter_results=filter_results,
            reason=reason
        )
        
        # Then
        assert quick_result.passed == passed
        assert quick_result.result == result
        assert quick_result.metrics == metrics
        assert quick_result.filter_results == filter_results
        assert quick_result.reason == reason
    
    @pytest.mark.unit
    def test_result_with_timeframe_fields(self):
        """타임프레임별 결과 필드 테스트"""
        # Given
        daily_result = Mock(spec=BacktestResult)
        hourly_result = Mock(spec=BacktestResult)
        minute_result = Mock(spec=BacktestResult)
        
        # When
        quick_result = QuickBacktestResult(
            passed=True,
            result=daily_result,
            metrics={'total_return': 10.0},
            filter_results={'return': True},
            reason="통과",
            daily_result=daily_result,
            hourly_result=hourly_result,
            minute_result=minute_result,
            daily_passed=True,
            hourly_passed=True,
            minute_passed=True
        )
        
        # Then
        assert quick_result.daily_result == daily_result
        assert quick_result.hourly_result == hourly_result
        assert quick_result.minute_result == minute_result
        assert quick_result.daily_passed is True
        assert quick_result.hourly_passed is True
        assert quick_result.minute_passed is True


class TestLoadTimeframeData:
    """_load_timeframe_data 메서드 테스트"""
    
    @pytest.mark.unit
    @patch('src.backtesting.quick_filter.HistoricalDataProvider')
    def test_load_timeframe_data_from_chart_data(self, mock_data_provider_class):
        """chart_data에서 타임프레임별 데이터 로드 테스트"""
        # Given
        ticker = 'KRW-ETH'
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        chart_data = {
            'day': pd.DataFrame({
                'open': [100 + i for i in range(30)],
                'high': [105 + i for i in range(30)],
                'low': [95 + i for i in range(30)],
                'close': [102 + i for i in range(30)],
                'volume': [1000 + i * 10 for i in range(30)]
            }, index=dates),
            'minute60': pd.DataFrame(),
            'minute15': pd.DataFrame()
        }
        config = QuickBacktestConfig(use_local_data=False, days=30)
        filter_instance = QuickBacktestFilter(config)
        
        # When
        result = filter_instance._load_timeframe_data(ticker, "day", chart_data)
        
        # Then
        assert result is not None
        assert len(result) == 30
        assert 'open' in result.columns
        assert 'close' in result.columns
    
    @pytest.mark.unit
    @patch('src.backtesting.quick_filter.HistoricalDataProvider')
    def test_load_timeframe_data_none_chart_data(self, mock_data_provider_class):
        """chart_data가 None일 때 테스트"""
        # Given
        ticker = 'KRW-ETH'
        config = QuickBacktestConfig(use_local_data=False, days=30)
        filter_instance = QuickBacktestFilter(config)
        
        # When
        result = filter_instance._load_timeframe_data(ticker, "day", None)
        
        # Then
        assert result is None


class TestRunSingleBacktest:
    """_run_single_backtest 메서드 테스트"""
    
    @pytest.mark.unit
    @patch('src.backtesting.quick_filter.BacktestRunner')
    def test_run_single_backtest_passed(self, mock_runner_class, mock_backtest_result_passed):
        """단일 타임프레임 백테스트 통과 테스트"""
        # Given
        ticker = 'KRW-ETH'
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        data = pd.DataFrame({
            'open': [100 + i for i in range(30)],
            'high': [105 + i for i in range(30)],
            'low': [95 + i for i in range(30)],
            'close': [102 + i for i in range(30)],
            'volume': [1000 + i * 10 for i in range(30)]
        }, index=dates)
        
        mock_runner_class.run_backtest = Mock(return_value=mock_backtest_result_passed)
        filter_instance = QuickBacktestFilter()
        
        # When
        result, passed, reason = filter_instance._run_single_backtest(
            ticker, data, "일봉"
        )
        
        # Then
        assert result is not None
        assert passed is True
        assert "통과" in reason or "모든" in reason
        assert mock_runner_class.run_backtest.called
    
    @pytest.mark.unit
    def test_run_single_backtest_insufficient_data(self):
        """데이터 부족 시 테스트"""
        # Given
        ticker = 'KRW-ETH'
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        data = pd.DataFrame({
            'open': [100 + i for i in range(5)],
            'high': [105 + i for i in range(5)],
            'low': [95 + i for i in range(5)],
            'close': [102 + i for i in range(5)],
            'volume': [1000 + i * 10 for i in range(5)]
        }, index=dates)
        
        filter_instance = QuickBacktestFilter()
        
        # When
        result, passed, reason = filter_instance._run_single_backtest(
            ticker, data, "일봉"
        )
        
        # Then
        assert result is None
        assert passed is False
        assert "부족" in reason or "10개" in reason

