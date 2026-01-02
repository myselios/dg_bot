"""
CoinScanStage 단위 테스트
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

from src.trading.pipeline.coin_scan_stage import CoinScanStage, create_multi_coin_trading_pipeline
from src.trading.pipeline.base_stage import PipelineContext, StageResult
from src.scanner.coin_selector import CoinCandidate, ScanResult
from src.scanner.multi_backtest import BacktestScore


class TestCoinScanStage:
    """CoinScanStage 클래스 테스트"""

    def test_initialization(self):
        """초기화 테스트"""
        stage = CoinScanStage(
            liquidity_top_n=30,
            min_volume_krw=20_000_000_000,
            backtest_top_n=10,
            final_select_n=3
        )

        assert stage.name == "CoinScan"
        assert stage.liquidity_top_n == 30
        assert stage.min_volume_krw == 20_000_000_000
        assert stage.backtest_top_n == 10
        assert stage.final_select_n == 3

    def test_initialization_default(self):
        """기본값 초기화 테스트"""
        stage = CoinScanStage()

        assert stage.liquidity_top_n == 20
        assert stage.min_volume_krw == 10_000_000_000
        assert stage.backtest_top_n == 5
        assert stage.final_select_n == 2

    @pytest.fixture
    def mock_context(self):
        """Mock 컨텍스트"""
        context = MagicMock(spec=PipelineContext)
        context.upbit_client = MagicMock()
        context.data_collector = MagicMock()
        context.trading_service = MagicMock()
        context.ai_service = MagicMock()
        context.ticker = "KRW-BTC"
        context.trading_mode = 'entry'
        context.portfolio_status = MagicMock()
        context.portfolio_status.positions = []
        return context

    @pytest.fixture
    def mock_scan_result_success(self):
        """성공적인 스캔 결과"""
        backtest_score = BacktestScore(
            ticker="KRW-ETH",
            symbol="ETH",
            passed=True,
            score=85.0,
            grade="STRONG PASS",
            metrics={'total_return': 25.0},
            filter_results={'return': True},
            reason="모든 조건 충족"
        )

        candidates = [
            CoinCandidate(
                ticker="KRW-ETH",
                symbol="ETH",
                coin_info=None,
                backtest_score=backtest_score,
                entry_signal=None,
                final_score=83.0,
                final_grade="BUY",
                selected=True,
                selection_reason="높은 백테스팅 점수"
            )
        ]

        return ScanResult(
            scan_time=datetime.now(),
            liquidity_scanned=20,
            backtest_passed=5,
            ai_analyzed=2,
            candidates=candidates,
            selected_coins=candidates,
            total_duration_seconds=30.5
        )

    @pytest.fixture
    def mock_scan_result_empty(self):
        """빈 스캔 결과"""
        return ScanResult(
            scan_time=datetime.now(),
            liquidity_scanned=20,
            backtest_passed=0,
            ai_analyzed=0,
            candidates=[],
            selected_coins=[],
            total_duration_seconds=15.0
        )

    def test_pre_execute_entry_mode(self, mock_context):
        """pre_execute - ENTRY 모드 테스트"""
        stage = CoinScanStage()
        mock_context.trading_mode = 'entry'

        result = stage.pre_execute(mock_context)

        assert result is True

    def test_pre_execute_management_mode(self, mock_context):
        """pre_execute - MANAGEMENT 모드 테스트 (스킵)"""
        stage = CoinScanStage()
        mock_context.trading_mode = 'management'

        result = stage.pre_execute(mock_context)

        assert result is False

    def test_pre_execute_no_mode(self, mock_context):
        """pre_execute - 모드 없음 테스트 (스킵)"""
        stage = CoinScanStage()
        mock_context.trading_mode = None

        result = stage.pre_execute(mock_context)

        assert result is False

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_context, mock_scan_result_success):
        """정상 실행 테스트"""
        stage = CoinScanStage()

        mock_selector = MagicMock()
        mock_selector.select_coins = AsyncMock(return_value=mock_scan_result_success)

        with patch.object(stage, '_get_coin_selector', return_value=mock_selector):
            result = await stage.execute(mock_context)

            assert result.success is True
            assert result.action == 'continue'
            assert mock_context.ticker == "KRW-ETH"

    @pytest.mark.asyncio
    async def test_execute_no_coins_found(self, mock_context, mock_scan_result_empty):
        """코인 없음 테스트"""
        stage = CoinScanStage()

        mock_selector = MagicMock()
        mock_selector.select_coins = AsyncMock(return_value=mock_scan_result_empty)

        with patch.object(stage, '_get_coin_selector', return_value=mock_selector):
            result = await stage.execute(mock_context)

            assert result.success is True
            assert result.action == 'skip'
            assert '진입 적합 코인 없음' in result.data['reason']

    @pytest.mark.asyncio
    async def test_execute_error_handling(self, mock_context):
        """에러 처리 테스트"""
        stage = CoinScanStage()

        with patch.object(stage, '_get_coin_selector') as mock_get_selector:
            mock_get_selector.side_effect = Exception("테스트 오류")

            result = await stage.execute(mock_context)

            assert result.success is False

    def test_get_held_tickers_empty(self, mock_context):
        """보유 코인 없음 테스트"""
        stage = CoinScanStage()
        mock_context.portfolio_status.positions = []
        mock_context.ticker = None

        tickers = stage._get_held_tickers(mock_context)

        assert tickers == []

    def test_get_held_tickers_with_positions(self, mock_context):
        """보유 코인 있음 테스트"""
        stage = CoinScanStage()

        pos1 = MagicMock()
        pos1.ticker = "KRW-BTC"
        pos2 = MagicMock()
        pos2.ticker = "KRW-ETH"

        mock_context.portfolio_status.positions = [pos1, pos2]
        mock_context.ticker = "KRW-XRP"

        tickers = stage._get_held_tickers(mock_context)

        assert "KRW-BTC" in tickers
        assert "KRW-ETH" in tickers
        assert "KRW-XRP" in tickers

    def test_get_held_tickers_no_duplicates(self, mock_context):
        """중복 티커 제거 테스트"""
        stage = CoinScanStage()

        pos = MagicMock()
        pos.ticker = "KRW-BTC"

        mock_context.portfolio_status.positions = [pos]
        mock_context.ticker = "KRW-BTC"  # 동일한 티커

        tickers = stage._get_held_tickers(mock_context)

        assert len(tickers) == 1
        assert tickers[0] == "KRW-BTC"

    def test_get_coin_selector_lazy_init(self):
        """코인 선택기 지연 초기화 테스트"""
        stage = CoinScanStage()

        assert stage._coin_selector is None

        with patch('src.trading.pipeline.coin_scan_stage.LiquidityScanner'):
            with patch('src.trading.pipeline.coin_scan_stage.HistoricalDataSync'):
                with patch('src.trading.pipeline.coin_scan_stage.MultiCoinBacktest'):
                    with patch('src.trading.pipeline.coin_scan_stage.CoinSelector') as MockSelector:
                        MockSelector.return_value = MagicMock()

                        selector1 = stage._get_coin_selector()
                        selector2 = stage._get_coin_selector()

                        # 같은 인스턴스여야 함
                        assert selector1 is selector2
                        # 한 번만 생성
                        assert MockSelector.call_count == 1


class TestCreateMultiCoinTradingPipeline:
    """create_multi_coin_trading_pipeline 함수 테스트"""

    def test_create_pipeline_default(self):
        """기본 파이프라인 생성 테스트"""
        # 실제 파이프라인 생성 (내부 import 사용)
        # Note: create_multi_coin_trading_pipeline은 deprecated이며
        # create_hybrid_trading_pipeline(enable_scanning=True)로 위임됨
        # HybridRiskCheckStage가 AdaptiveRiskCheck와 CoinScan을 통합
        pipeline = create_multi_coin_trading_pipeline()

        assert pipeline is not None
        # 스테이지: HybridRiskCheck -> DataCollection -> Analysis -> Execution
        assert len(pipeline.stages) == 4

    def test_create_pipeline_custom_params(self):
        """커스텀 파라미터로 파이프라인 생성"""
        pipeline = create_multi_coin_trading_pipeline(
            stop_loss_pct=-7.0,
            take_profit_pct=15.0,
            max_positions=5,
            liquidity_top_n=30,
            backtest_top_n=10
        )

        assert pipeline is not None
        # 스테이지: HybridRiskCheck -> DataCollection -> Analysis -> Execution
        assert len(pipeline.stages) == 4

    def test_pipeline_stage_names(self):
        """파이프라인 스테이지 이름 확인"""
        pipeline = create_multi_coin_trading_pipeline()

        stage_names = [s.name for s in pipeline.stages]

        # 순서: HybridRiskCheck -> DataCollection -> Analysis -> Execution
        # (HybridRiskCheckStage가 AdaptiveRiskCheck와 CoinScan을 통합)
        assert 'HybridRiskCheck' in stage_names
        assert 'DataCollection' in stage_names
