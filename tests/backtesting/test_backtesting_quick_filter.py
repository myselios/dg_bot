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
    BacktestConfig,
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
    """필터링 통과 Mock 백테스트 결과 (Phase 7 가중 필터 기준)"""
    return BacktestResult(
        initial_capital=10_000_000,
        final_equity=11_500_000,
        equity_curve=[10_000_000 + i * 50000 for i in range(35)],
        trades=[],
        metrics={
            'total_return': 20.0,      # 20% 수익률 (>= 9%)
            'win_rate': 45.0,          # 45% 승률 (>= 35%)
            'sharpe_ratio': 1.5,       # 1.5 (>= 0.7)
            'sortino_ratio': 1.5,      # 1.5 (>= 0.9)
            'calmar_ratio': 1.0,       # 1.0 (>= 0.4)
            'max_drawdown': -10.0,     # -10% (<= 25%)
            'total_trades': 35,        # 35 (>= 30, CLT 기준)
            'profit_factor': 2.0,      # 2.0 (>= 1.5)
            'final_equity': 11_500_000,
            'volatility': 40.0,        # 40% (<= 80%)
            'winning_trades': 16,
            'losing_trades': 19,
            'avg_win': 3.5,            # 3.5% 평균 수익 (백분율 기준, R=1.75)
            'avg_loss': -2.0,          # 2.0% 평균 손실 (expectancy 양수 확보)
            'max_consecutive_wins': 4,
            'max_consecutive_losses': 3,  # 3 (<= 6)
            'avg_holding_period_hours': 100.0,  # 100h (<= 240h)
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


class TestBacktestConfig:
    """BacktestConfig 테스트"""
    
    @pytest.mark.unit
    def test_default_config(self):
        """기본 설정 테스트"""
        # When
        config = BacktestConfig()

        # Then
        assert config.days == 730  # 2년
        assert config.use_local_data == True
        assert config.initial_capital == 10_000_000
        assert config.commission == 0.0005
        assert config.slippage == 0.0001
        # Phase 7 가중 필터 시스템 기본값
        assert config.min_return == 9.0  # 2년간 9%
        assert config.min_win_rate == 35.0  # 35%
        assert config.min_sharpe_ratio == 0.7  # 0.7
        assert config.max_drawdown == 25.0  # 25%
    
    @pytest.mark.unit
    def test_custom_config(self):
        """커스텀 설정 테스트"""
        # When
        config = BacktestConfig(
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
        assert isinstance(filter_instance.config, BacktestConfig)
        assert filter_instance.data_provider is not None
    
    @pytest.mark.unit
    def test_filter_initialization_with_custom_config(self):
        """커스텀 설정으로 필터 초기화 테스트"""
        # Given
        config = BacktestConfig(min_return=10.0)
        
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
        
        config = BacktestConfig(use_local_data=False, days=30)
        filter_instance = QuickBacktestFilter(config)
        
        # When
        result = filter_instance.run_quick_backtest(ticker, sample_30day_data)
        
        # Then
        assert isinstance(result, QuickBacktestResult)
        assert result.passed is True
        assert result.result is not None
        assert 'total_return' in result.metrics
        assert result.metrics['total_return'] == 20.0  # mock_backtest_result_passed의 값
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
        
        config = BacktestConfig(use_local_data=False, days=30)
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
        config = BacktestConfig(use_local_data=False, days=30)
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
        config = BacktestConfig(use_local_data=False, days=30)
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
        """모든 필터 조건 통과 테스트 (Phase 7 가중 필터 기준)"""
        # Given
        filter_instance = QuickBacktestFilter()
        metrics = {
            'total_return': 20.0,  # >= 9.0
            'win_rate': 45.0,  # >= 35.0
            'profit_factor': 2.0,  # >= 1.5
            'sharpe_ratio': 1.5,  # >= 0.7
            'sortino_ratio': 1.5,  # >= 0.9
            'calmar_ratio': 1.0,  # >= 0.4
            'max_drawdown': -10.0,  # <= 25.0
            'max_consecutive_losses': 3,  # <= 6
            'volatility': 40.0,  # <= 80.0
            'total_trades': 35,  # >= 30 (CLT 기준)
            'avg_win': 200000,  # avg_win/avg_loss >= 1.0
            'avg_loss': -100000,
            'avg_holding_period_hours': 100.0  # <= 240.0
        }

        # When
        filter_results = filter_instance._check_filters(metrics)

        # Then - 12가지 필터 조건 체크
        assert filter_results['return'] is True
        assert filter_results['win_rate'] is True
        assert filter_results['profit_factor'] is True
        assert filter_results['sharpe_ratio'] is True
        assert filter_results['sortino_ratio'] is True
        assert filter_results['calmar_ratio'] is True
        assert filter_results['max_drawdown'] is True
        assert filter_results['max_consecutive_losses'] is True
        assert filter_results['volatility'] is True
        assert filter_results['min_trades'] is True
        assert filter_results['avg_win_loss_ratio'] is True
        assert filter_results['avg_holding_hours'] is True
    
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
            'total_return': 20.0,
            'win_rate': 30.0,  # 38% 미만
            'profit_factor': 2.0,
            'sharpe_ratio': 1.5,
            'sortino_ratio': 1.5,
            'calmar_ratio': 1.0,
            'max_drawdown': -10.0,
            'max_consecutive_losses': 3,
            'volatility': 40.0,
            'total_trades': 25,
            'avg_win': 200000,
            'avg_loss': -100000,
            'avg_holding_period_hours': 100.0
        }

        # When
        filter_results = filter_instance._check_filters(metrics)

        # Then
        assert filter_results['return'] is True
        assert filter_results['win_rate'] is False  # 30% < 38%
        assert filter_results['sharpe_ratio'] is True
        assert filter_results['max_drawdown'] is True
    
    @pytest.mark.unit
    def test_check_filters_failed_sharpe(self):
        """Sharpe Ratio 필터 실패 테스트"""
        # Given
        filter_instance = QuickBacktestFilter()
        metrics = {
            'total_return': 20.0,
            'win_rate': 45.0,
            'profit_factor': 2.0,
            'sharpe_ratio': 0.5,  # 1.0 미만
            'sortino_ratio': 1.5,
            'calmar_ratio': 1.0,
            'max_drawdown': -10.0,
            'max_consecutive_losses': 3,
            'volatility': 40.0,
            'total_trades': 25,
            'avg_win': 200000,
            'avg_loss': -100000,
            'avg_holding_period_hours': 100.0
        }

        # When
        filter_results = filter_instance._check_filters(metrics)

        # Then
        assert filter_results['return'] is True
        assert filter_results['win_rate'] is True
        assert filter_results['sharpe_ratio'] is False  # 0.5 < 1.0
        assert filter_results['max_drawdown'] is True
    
    @pytest.mark.unit
    def test_check_filters_failed_drawdown(self):
        """Max Drawdown 필터 실패 테스트 (Phase 7: max_drawdown=25%)"""
        # Given
        filter_instance = QuickBacktestFilter()
        metrics = {
            'total_return': 20.0,
            'win_rate': 45.0,
            'profit_factor': 2.0,
            'sharpe_ratio': 1.5,
            'sortino_ratio': 1.5,
            'calmar_ratio': 1.0,
            'max_drawdown': -30.0,  # -30% (25% 초과)
            'max_consecutive_losses': 3,
            'volatility': 40.0,
            'total_trades': 35,
            'avg_win': 200000,
            'avg_loss': -100000,
            'avg_holding_period_hours': 100.0
        }

        # When
        filter_results = filter_instance._check_filters(metrics)

        # Then
        assert filter_results['return'] is True
        assert filter_results['win_rate'] is True
        assert filter_results['sharpe_ratio'] is True
        assert filter_results['max_drawdown'] is False  # 30% > 25%
    
    @pytest.mark.unit
    def test_check_filters_boundary_values(self):
        """경계값 테스트 (Phase 7 가중 필터 경계값)"""
        # Given
        filter_instance = QuickBacktestFilter()
        metrics = {
            'total_return': 9.0,       # 정확히 9%
            'win_rate': 35.0,          # 정확히 35%
            'profit_factor': 1.5,      # 정확히 1.5
            'sharpe_ratio': 0.7,       # 정확히 0.7
            'sortino_ratio': 0.9,      # 정확히 0.9
            'calmar_ratio': 0.4,       # 정확히 0.4
            'max_drawdown': -25.0,     # 정확히 -25%
            'max_consecutive_losses': 6,  # 정확히 6
            'volatility': 80.0,        # 정확히 80%
            'total_trades': 30,        # 정확히 30 (CLT 기준)
            'avg_win': 100000,         # 100000/100000 = 1.0
            'avg_loss': -100000,
            'avg_holding_period_hours': 240.0  # 정확히 240h
        }

        # When
        filter_results = filter_instance._check_filters(metrics)

        # Then (경계값 포함이므로 모두 True)
        assert filter_results['return'] is True
        assert filter_results['win_rate'] is True
        assert filter_results['profit_factor'] is True
        assert filter_results['sharpe_ratio'] is True
        assert filter_results['sortino_ratio'] is True
        assert filter_results['calmar_ratio'] is True
        assert filter_results['max_drawdown'] is True
        assert filter_results['max_consecutive_losses'] is True
        assert filter_results['volatility'] is True
        assert filter_results['min_trades'] is True
        assert filter_results['avg_win_loss_ratio'] is True
        assert filter_results['avg_holding_hours'] is True
    
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
        config = BacktestConfig(use_local_data=False, days=30)
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
        config = BacktestConfig(use_local_data=False, days=30)
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

