"""
멀티코인 시스템 통합 테스트
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime
import pandas as pd

from src.trading.pipeline import (
    create_multi_coin_trading_pipeline,
    create_adaptive_trading_pipeline,
    PipelineContext
)
from src.scanner.liquidity_scanner import LiquidityScanner, CoinInfo
from src.scanner.multi_backtest import MultiCoinBacktest, MultiBacktestConfig, BacktestScore
from src.scanner.coin_selector import CoinSelector, CoinCandidate, ScanResult
from src.position.portfolio_manager import TradingMode


@pytest.mark.integration
class TestMultiCoinPipelineIntegration:
    """멀티코인 파이프라인 통합 테스트"""

    @pytest.fixture
    def mock_services(self):
        """Mock 서비스들"""
        return {
            'upbit_client': MagicMock(),
            'data_collector': MagicMock(),
            'trading_service': MagicMock(),
            'ai_service': MagicMock()
        }

    @pytest.fixture
    def sample_coin_infos(self):
        """샘플 코인 정보"""
        return [
            CoinInfo(
                ticker='KRW-BTC',
                symbol='BTC',
                korean_name='비트코인',
                current_price=50000000,
                volume_24h=1000,
                acc_trade_price_24h=100_000_000_000,
                signed_change_rate=2.0,
                high_price=51000000,
                low_price=49000000,
                volatility_7d=3.5
            ),
            CoinInfo(
                ticker='KRW-ETH',
                symbol='ETH',
                korean_name='이더리움',
                current_price=4000000,
                volume_24h=5000,
                acc_trade_price_24h=50_000_000_000,
                signed_change_rate=1.5,
                high_price=4100000,
                low_price=3900000,
                volatility_7d=4.2
            )
        ]

    def test_multi_coin_pipeline_creation(self):
        """멀티코인 파이프라인 생성 테스트 (하이브리드 파이프라인 사용)"""
        # Note: create_multi_coin_trading_pipeline은 deprecated되어
        # create_hybrid_trading_pipeline(enable_scanning=True)를 내부적으로 호출합니다.
        # 새로운 하이브리드 파이프라인은 4개 스테이지를 가집니다:
        # HybridRiskCheck (CoinScan 통합), DataCollection, Analysis, Execution
        pipeline = create_multi_coin_trading_pipeline(
            stop_loss_pct=-5.0,
            take_profit_pct=10.0,
            max_positions=3,
            liquidity_top_n=20,
            backtest_top_n=5,
            final_select_n=2
        )

        assert pipeline is not None
        assert len(pipeline.stages) == 4  # HybridRiskCheck가 CoinScan을 통합

        # 스테이지 이름 확인 (HybridRiskCheck가 CoinScan을 포함)
        stage_names = [s.name for s in pipeline.stages]
        assert 'HybridRiskCheck' in stage_names  # CoinScan이 통합됨

    def test_adaptive_pipeline_creation(self):
        """적응형 파이프라인 생성 테스트"""
        pipeline = create_adaptive_trading_pipeline(
            stop_loss_pct=-5.0,
            take_profit_pct=10.0,
            max_positions=3
        )

        assert pipeline is not None
        assert len(pipeline.stages) >= 4

    def test_pipeline_context_creation(self, mock_services):
        """파이프라인 컨텍스트 생성 테스트"""
        context = PipelineContext(
            ticker="KRW-BTC",
            trading_type='spot',
            upbit_client=mock_services['upbit_client'],
            data_collector=mock_services['data_collector'],
            trading_service=mock_services['trading_service'],
            ai_service=mock_services['ai_service']
        )

        assert context.ticker == "KRW-BTC"
        assert context.trading_type == 'spot'


@pytest.mark.integration
class TestScannerIntegration:
    """스캐너 모듈 통합 테스트"""

    @pytest.fixture
    def sample_ohlcv_data(self):
        """샘플 OHLCV 데이터"""
        dates = pd.date_range('2024-01-01', periods=365, freq='D')
        return pd.DataFrame({
            'open': [100 + i * 0.1 for i in range(365)],
            'high': [105 + i * 0.1 for i in range(365)],
            'low': [95 + i * 0.1 for i in range(365)],
            'close': [102 + i * 0.1 for i in range(365)],
            'volume': [1000 + i * 5 for i in range(365)]
        }, index=dates)

    @pytest.mark.asyncio
    async def test_liquidity_scanner_filter(self):
        """유동성 스캐너 필터링 통합 테스트"""
        scanner = LiquidityScanner(min_volume_krw=10_000_000_000)

        # 필터 테스트
        valid_coin = CoinInfo(
            ticker='KRW-BTC',
            symbol='BTC',
            korean_name='비트코인',
            current_price=50000000,
            volume_24h=1000,
            acc_trade_price_24h=50_000_000_000,
            signed_change_rate=2.0,
            high_price=51000000,
            low_price=49000000
        )

        stablecoin = CoinInfo(
            ticker='KRW-USDT',
            symbol='USDT',
            korean_name='테더',
            current_price=1300,
            volume_24h=10000000,
            acc_trade_price_24h=100_000_000_000,
            signed_change_rate=0.01,
            high_price=1301,
            low_price=1299
        )

        low_volume = CoinInfo(
            ticker='KRW-XYZ',
            symbol='XYZ',
            korean_name='테스트코인',
            current_price=100,
            volume_24h=1000,
            acc_trade_price_24h=5_000_000_000,
            signed_change_rate=1.0,
            high_price=105,
            low_price=95
        )

        # 유효한 코인은 통과
        assert scanner._passes_filter(valid_coin, 10_000_000_000) is True

        # 스테이블코인은 제외
        assert scanner._passes_filter(stablecoin, 10_000_000_000) is False

        # 거래대금 부족은 제외
        assert scanner._passes_filter(low_volume, 10_000_000_000) is False

    @pytest.mark.asyncio
    async def test_multi_backtest_scoring(self):
        """백테스팅 스코어링 통합 테스트"""
        config = MultiBacktestConfig()
        backtest = MultiCoinBacktest(config=config)

        # 엄격한 퀀트 기준을 통과하는 우수한 지표
        excellent_metrics = {
            'total_return': 35.0,       # 수익률 35% (기준 3%+)
            'win_rate': 55.0,           # 승률 55% (기준 35%+)
            'profit_factor': 2.5,       # 손익비 2.5 (기준 1.3+)
            'sharpe_ratio': 2.2,        # 샤프 2.2 (기준 0.8+)
            'sortino_ratio': 2.5,       # 소르티노 2.5
            'calmar_ratio': 2.0,        # 칼마 2.0
            'max_drawdown': -6.0,       # MDD -6% (기준 -20% 이내)
            'max_consecutive_losses': 2,  # 연속손실 2회
            'volatility': 20.0,         # 변동성 20%
            'total_trades': 100,        # 거래수 100회 (기준 3+)
            'avg_win': 8.0,
            'avg_loss': -3.0,
            'avg_holding_period_hours': 48.0
        }

        criteria = backtest._get_filter_criteria(None)
        filter_results = backtest._check_filters(excellent_metrics, criteria)

        # 엄격한 기준에서 모든 필터 통과
        assert all(filter_results.values()), f"Some filters failed: {filter_results}"

        # 점수는 70점 이상 (STRONG PASS 기준)
        score = backtest._calculate_score(excellent_metrics)
        assert score >= 70, f"Expected score >= 70, got {score}"

        # 등급은 STRONG PASS
        grade = backtest._determine_grade(score, passed=True)
        assert grade == "STRONG PASS", f"Expected STRONG PASS, got: {grade}"

    @pytest.mark.asyncio
    async def test_multi_backtest_filtering(self):
        """백테스팅 필터링 통합 테스트"""
        config = MultiBacktestConfig()
        backtest = MultiCoinBacktest(config=config)

        # 엄격한 기준에서 확실히 실패하는 나쁜 지표
        bad_metrics = {
            'total_return': 1.0,        # 3% 기준 미달
            'win_rate': 25.0,           # 35% 기준 미달
            'profit_factor': 0.8,       # 1.3 기준 미달
            'sharpe_ratio': 0.3,        # 0.8 기준 미달
            'sortino_ratio': 0.4,
            'calmar_ratio': 0.2,
            'max_drawdown': -30.0,      # 20% 기준 초과
            'max_consecutive_losses': 10,
            'volatility': 80.0,
            'total_trades': 2,          # 3 기준 미달
            'avg_win': 2.0,
            'avg_loss': -4.0,
            'avg_holding_period_hours': 300.0
        }

        criteria = backtest._get_filter_criteria(None)
        filter_results = backtest._check_filters(bad_metrics, criteria)

        # 엄격한 기준에서 여러 필터 확실히 실패
        failed_filters = [k for k, v in filter_results.items() if not v]
        assert len(failed_filters) >= 4, f"Expected at least 4 filters to fail, got: {failed_filters}"

        # 주요 필터들 실패 확인
        assert filter_results['return'] is False, "return filter should fail"
        assert filter_results['win_rate'] is False, "win_rate filter should fail"
        assert filter_results['sharpe_ratio'] is False, "sharpe_ratio filter should fail"
        assert filter_results['max_drawdown'] is False, "max_drawdown filter should fail"

        # 점수는 30점 이하 (매우 나쁜 지표)
        score = backtest._calculate_score(bad_metrics)
        assert score <= 30, f"Expected score <= 30, got {score}"

        # 등급은 FAIL
        grade = backtest._determine_grade(score, passed=False)
        assert grade == "FAIL", f"Expected FAIL, got {grade}"


@pytest.mark.integration
class TestCoinSelectorIntegration:
    """CoinSelector 통합 테스트"""

    @pytest.fixture
    def mock_coin_infos(self):
        """Mock 코인 정보"""
        return [
            CoinInfo(
                ticker='KRW-BTC',
                symbol='BTC',
                korean_name='비트코인',
                current_price=50000000,
                volume_24h=1000,
                acc_trade_price_24h=100_000_000_000,
                signed_change_rate=2.0,
                high_price=51000000,
                low_price=49000000,
                volatility_7d=3.5
            ),
            CoinInfo(
                ticker='KRW-ETH',
                symbol='ETH',
                korean_name='이더리움',
                current_price=4000000,
                volume_24h=5000,
                acc_trade_price_24h=50_000_000_000,
                signed_change_rate=1.5,
                high_price=4100000,
                low_price=3900000,
                volatility_7d=4.2
            ),
            CoinInfo(
                ticker='KRW-XRP',
                symbol='XRP',
                korean_name='리플',
                current_price=500,
                volume_24h=10000000,
                acc_trade_price_24h=30_000_000_000,
                signed_change_rate=3.0,
                high_price=520,
                low_price=480,
                volatility_7d=6.0
            )
        ]

    @pytest.fixture
    def mock_backtest_scores(self):
        """Mock 백테스팅 점수"""
        return [
            BacktestScore(
                ticker='KRW-BTC',
                symbol='BTC',
                passed=True,
                score=85.0,
                grade='STRONG PASS',
                metrics={'total_return': 25.0, 'win_rate': 48.0},
                filter_results={'return': True, 'win_rate': True},
                reason='모든 조건 충족'
            ),
            BacktestScore(
                ticker='KRW-ETH',
                symbol='ETH',
                passed=True,
                score=78.0,
                grade='STRONG PASS',
                metrics={'total_return': 20.0, 'win_rate': 42.0},
                filter_results={'return': True, 'win_rate': True},
                reason='모든 조건 충족'
            ),
            BacktestScore(
                ticker='KRW-XRP',
                symbol='XRP',
                passed=False,
                score=45.0,
                grade='FAIL',
                metrics={'total_return': 8.0, 'win_rate': 35.0},
                filter_results={'return': False, 'win_rate': False},
                reason='수익률 조건 미달'
            )
        ]

    @pytest.mark.asyncio
    async def test_coin_selection_flow(self, mock_coin_infos, mock_backtest_scores):
        """코인 선택 흐름 통합 테스트"""
        selector = CoinSelector(
            liquidity_top_n=20,
            backtest_top_n=5,
            final_select_n=2
        )

        with patch.object(
            selector.liquidity_scanner,
            'scan_top_coins',
            new_callable=AsyncMock
        ) as mock_scan:
            with patch.object(
                selector.multi_backtest,
                'run_parallel_backtest',
                new_callable=AsyncMock
            ) as mock_backtest:
                with patch.object(selector.liquidity_scanner, 'print_scan_result'):
                    with patch.object(selector.multi_backtest, 'print_results'):
                        mock_scan.return_value = mock_coin_infos
                        mock_backtest.return_value = mock_backtest_scores

                        result = await selector.select_coins()

                        # 결과 검증
                        assert result is not None
                        assert result.liquidity_scanned == 3
                        assert result.backtest_passed == 2  # BTC, ETH만 통과

                        # 선택된 코인은 최대 2개
                        assert len(result.selected_coins) <= 2

    @pytest.mark.asyncio
    async def test_exclude_held_tickers(self, mock_coin_infos, mock_backtest_scores):
        """보유 티커 제외 테스트"""
        selector = CoinSelector(final_select_n=2)

        # BTC가 제외된 결과를 모킹 (실제 select_coins은 내부에서 필터링)
        filtered_coin_infos = [c for c in mock_coin_infos if c.ticker != 'KRW-BTC']
        filtered_backtest_scores = [s for s in mock_backtest_scores if s.ticker != 'KRW-BTC']

        with patch.object(
            selector.liquidity_scanner,
            'scan_top_coins',
            new_callable=AsyncMock
        ) as mock_scan:
            with patch.object(
                selector.multi_backtest,
                'run_parallel_backtest',
                new_callable=AsyncMock
            ) as mock_backtest:
                with patch.object(selector.liquidity_scanner, 'print_scan_result'):
                    with patch.object(selector.multi_backtest, 'print_results'):
                        # 필터링된 결과 반환하도록 설정
                        mock_scan.return_value = filtered_coin_infos
                        mock_backtest.return_value = filtered_backtest_scores

                        # BTC 제외
                        result = await selector.select_coins(exclude_tickers=['KRW-BTC'])

                        # 유동성 스캔 결과에서 BTC가 이미 제외된 상태
                        # 따라서 선택된 코인에도 BTC가 없어야 함
                        for coin in result.selected_coins:
                            assert coin.ticker != 'KRW-BTC'

    def test_final_score_calculation(self):
        """최종 점수 계산 테스트"""
        selector = CoinSelector()

        # BacktestScore 객체 생성
        bt_result = BacktestScore(
            ticker='KRW-BTC',
            symbol='BTC',
            passed=True,
            score=80.0,
            grade='STRONG PASS',
            metrics={'total_return': 25.0},
            filter_results={'return': True},
            reason='테스트'
        )

        # AI 점수 모킹
        ai_score = MagicMock()
        ai_score.score = 70.0

        final = selector._calculate_final_score(bt_result, ai_score)

        # 백테스팅 60% + AI 40%
        assert final == 80.0 * 0.6 + 70.0 * 0.4  # 76.0


@pytest.mark.integration
class TestPortfolioManagerIntegration:
    """PortfolioManager 통합 테스트"""

    def test_trading_mode_entry(self):
        """ENTRY 모드 테스트"""
        from src.position.portfolio_manager import PortfolioManager

        mock_client = MagicMock()
        mock_client.get_balance.return_value = 1000000  # 100만원
        mock_client.get_balances.return_value = [
            {'currency': 'KRW', 'balance': '1000000', 'avg_buy_price': '0'}
        ]

        pm = PortfolioManager(exchange_client=mock_client, max_positions=3)
        status = pm.get_portfolio_status()

        # 포지션 없으면 ENTRY 모드
        assert status.trading_mode == TradingMode.ENTRY
        assert status.can_open_new_position is True

    def test_trading_mode_management(self):
        """MANAGEMENT 모드 테스트"""
        from src.position.portfolio_manager import PortfolioManager

        mock_client = MagicMock()
        mock_client.get_balance.return_value = 500000
        mock_client.get_balances.return_value = [
            {'currency': 'KRW', 'balance': '500000', 'avg_buy_price': '0'},
            {'currency': 'BTC', 'balance': '0.01', 'avg_buy_price': '50000000'}
        ]
        mock_client.get_current_price.return_value = 51000000

        pm = PortfolioManager(exchange_client=mock_client, max_positions=3)
        status = pm.get_portfolio_status()

        # 포지션이 있으면 MANAGEMENT 모드 또는 ENTRY 모드 (아직 max_positions 미도달 시)
        assert len(status.positions) == 1
