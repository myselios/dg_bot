"""
CoinSelector 단위 테스트
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

from src.scanner.coin_selector import CoinSelector, CoinCandidate, ScanResult
from src.scanner.liquidity_scanner import CoinInfo
from src.scanner.multi_backtest import BacktestScore


class TestCoinCandidate:
    """CoinCandidate 데이터클래스 테스트"""

    def test_candidate_creation(self):
        """CoinCandidate 객체 생성 테스트"""
        backtest_score = BacktestScore(
            ticker="KRW-BTC",
            symbol="BTC",
            passed=True,
            score=85.0,
            grade="STRONG PASS",
            metrics={'total_return': 25.0},
            filter_results={'return': True},
            reason="모든 조건 충족"
        )

        candidate = CoinCandidate(
            ticker="KRW-BTC",
            symbol="BTC",
            coin_info=None,
            backtest_score=backtest_score,
            entry_signal=None,
            final_score=83.0,
            final_grade="BUY",
            selected=True,
            selection_reason="높은 백테스팅 점수"
        )

        assert candidate.ticker == "KRW-BTC"
        assert candidate.symbol == "BTC"
        assert candidate.final_score == 83.0
        assert candidate.final_grade == "BUY"
        assert candidate.selected is True

    def test_candidate_is_ready_for_entry_true(self):
        """진입 준비 완료 테스트 - True"""
        entry_signal = MagicMock()
        entry_signal.decision = 'buy'

        candidate = CoinCandidate(
            ticker="KRW-BTC",
            symbol="BTC",
            coin_info=None,
            backtest_score=None,
            entry_signal=entry_signal,
            final_score=80.0,
            final_grade="BUY",
            selected=True,
            selection_reason="테스트"
        )

        assert candidate.is_ready_for_entry is True

    def test_candidate_is_ready_for_entry_false_not_selected(self):
        """진입 준비 완료 테스트 - 선택 안됨"""
        entry_signal = MagicMock()
        entry_signal.decision = 'buy'

        candidate = CoinCandidate(
            ticker="KRW-BTC",
            symbol="BTC",
            coin_info=None,
            backtest_score=None,
            entry_signal=entry_signal,
            final_score=80.0,
            final_grade="BUY",
            selected=False,
            selection_reason="테스트"
        )

        assert candidate.is_ready_for_entry is False


class TestScanResult:
    """ScanResult 데이터클래스 테스트"""

    def test_scan_result_creation(self):
        """ScanResult 객체 생성 테스트"""
        candidate = CoinCandidate(
            ticker="KRW-BTC",
            symbol="BTC",
            coin_info=None,
            backtest_score=None,
            entry_signal=None,
            final_score=80.0,
            final_grade="BUY",
            selected=True,
            selection_reason="테스트"
        )

        result = ScanResult(
            scan_time=datetime.now(),
            liquidity_scanned=20,
            backtest_passed=5,
            ai_analyzed=3,
            candidates=[candidate],
            selected_coins=[candidate],
            total_duration_seconds=30.5
        )

        assert result.liquidity_scanned == 20
        assert result.backtest_passed == 5
        assert result.ai_analyzed == 3
        assert len(result.selected_coins) == 1

    def test_scan_result_empty(self):
        """빈 스캔 결과 테스트"""
        result = ScanResult(
            scan_time=datetime.now(),
            liquidity_scanned=0,
            backtest_passed=0,
            ai_analyzed=0,
            candidates=[],
            selected_coins=[],
            total_duration_seconds=1.0
        )

        assert len(result.selected_coins) == 0


class TestCoinSelector:
    """CoinSelector 클래스 테스트"""

    def test_initialization_default(self):
        """기본값 초기화 테스트"""
        selector = CoinSelector()

        assert selector.liquidity_top_n == 20
        assert selector.min_volume_krw == 10_000_000_000
        assert selector.backtest_top_n == 5
        assert selector.ai_top_n == 5
        assert selector.final_select_n == 2

    def test_initialization_custom(self):
        """커스텀 값 초기화 테스트"""
        selector = CoinSelector(
            liquidity_top_n=30,
            min_volume_krw=20_000_000_000,
            backtest_top_n=10,
            ai_top_n=3,
            final_select_n=3
        )

        assert selector.liquidity_top_n == 30
        assert selector.min_volume_krw == 20_000_000_000
        assert selector.backtest_top_n == 10
        assert selector.ai_top_n == 3
        assert selector.final_select_n == 3

    def test_calculate_final_score(self):
        """최종 점수 계산 테스트"""
        selector = CoinSelector()

        # BacktestScore 객체 생성
        bt_result = BacktestScore(
            ticker="KRW-BTC",
            symbol="BTC",
            passed=True,
            score=80.0,
            grade="STRONG PASS",
            metrics={'total_return': 20.0},
            filter_results={'return': True},
            reason="테스트"
        )

        # EntrySignal 객체 모킹
        entry_signal = MagicMock()
        entry_signal.score = 70.0

        final_score = selector._calculate_final_score(bt_result, entry_signal)

        # 백테스팅 60% + AI 40%
        expected = 80.0 * 0.6 + 70.0 * 0.4  # 76.0
        assert final_score == expected

    def test_calculate_final_score_no_ai(self):
        """AI 없이 최종 점수 계산 테스트"""
        selector = CoinSelector()

        # BacktestScore 객체 생성
        bt_result = BacktestScore(
            ticker="KRW-BTC",
            symbol="BTC",
            passed=True,
            score=80.0,
            grade="STRONG PASS",
            metrics={'total_return': 20.0},
            filter_results={'return': True},
            reason="테스트"
        )

        final_score = selector._calculate_final_score(bt_result, None)

        # 백테스팅 60% + AI 추정 40% (STRONG PASS = 70점)
        expected = 80.0 * 0.6 + 70.0 * 0.4  # 76.0
        assert final_score == expected

    def test_determine_final_grade_strong_buy(self):
        """최종 등급 결정 테스트 - STRONG BUY"""
        selector = CoinSelector()

        bt_result = BacktestScore(
            ticker="KRW-BTC",
            symbol="BTC",
            passed=True,
            score=85.0,
            grade="STRONG PASS",
            metrics={},
            filter_results={},
            reason="테스트"
        )

        entry_signal = MagicMock()
        entry_signal.decision = 'buy'
        entry_signal.confidence = 'high'

        grade = selector._determine_final_grade(bt_result, entry_signal, 75.0)

        assert grade == "STRONG BUY"

    def test_should_select_true(self):
        """선택 여부 결정 테스트 - True"""
        selector = CoinSelector()

        bt_result = BacktestScore(
            ticker="KRW-BTC",
            symbol="BTC",
            passed=True,
            score=80.0,
            grade="STRONG PASS",
            metrics={},
            filter_results={},
            reason="테스트"
        )

        entry_signal = MagicMock()
        entry_signal.decision = 'buy'

        should_select = selector._should_select(bt_result, entry_signal, 70.0)

        assert should_select is True

    def test_should_select_false_not_passed(self):
        """선택 여부 결정 테스트 - 백테스팅 미통과"""
        selector = CoinSelector()

        bt_result = BacktestScore(
            ticker="KRW-BTC",
            symbol="BTC",
            passed=False,
            score=30.0,
            grade="FAIL",
            metrics={},
            filter_results={},
            reason="테스트"
        )

        should_select = selector._should_select(bt_result, None, 30.0)

        assert should_select is False


@pytest.mark.asyncio
class TestCoinSelectorAsync:
    """CoinSelector 비동기 메서드 테스트"""

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
            )
        ]

    async def test_select_coins_success(self, mock_coin_infos, mock_backtest_scores):
        """코인 선택 성공 테스트"""
        selector = CoinSelector(final_select_n=2)

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

                        assert result is not None
                        assert result.liquidity_scanned == 2
                        assert result.backtest_passed == 2

    async def test_select_coins_no_liquidity(self):
        """유동성 코인 없음 테스트"""
        selector = CoinSelector()

        with patch.object(
            selector.liquidity_scanner,
            'scan_top_coins',
            new_callable=AsyncMock
        ) as mock_scan:
            mock_scan.return_value = []

            result = await selector.select_coins()

            assert result.liquidity_scanned == 0
            assert len(result.selected_coins) == 0

    async def test_select_coins_no_backtest_pass(self, mock_coin_infos):
        """백테스팅 통과 코인 없음 테스트"""
        selector = CoinSelector()

        failed_score = BacktestScore(
            ticker='KRW-BTC',
            symbol='BTC',
            passed=False,
            score=20.0,
            grade='FAIL',
            metrics={},
            filter_results={'return': False},
            reason='수익률 미달'
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
                    mock_scan.return_value = mock_coin_infos
                    mock_backtest.return_value = [failed_score]

                    result = await selector.select_coins()

                    assert result.backtest_passed == 0
                    assert len(result.selected_coins) == 0

    async def test_select_coins_exclude_tickers(self, mock_coin_infos, mock_backtest_scores):
        """보유 티커 제외 테스트"""
        selector = CoinSelector(final_select_n=2)

        # ETH만 반환 (BTC 제외)
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
                        mock_scan.return_value = mock_coin_infos
                        mock_backtest.return_value = filtered_backtest_scores

                        result = await selector.select_coins(exclude_tickers=['KRW-BTC'])

                        # BTC가 제외된 결과여야 함
                        for coin in result.selected_coins:
                            assert coin.ticker != 'KRW-BTC'

    async def test_select_coins_with_data_sync(self, mock_coin_infos, mock_backtest_scores):
        """데이터 동기화 포함 테스트"""
        selector = CoinSelector()

        with patch.object(
            selector.liquidity_scanner,
            'scan_top_coins',
            new_callable=AsyncMock
        ) as mock_scan:
            with patch.object(
                selector.data_sync,
                'sync_multiple_coins',
                new_callable=AsyncMock
            ) as mock_sync:
                with patch.object(
                    selector.multi_backtest,
                    'run_parallel_backtest',
                    new_callable=AsyncMock
                ) as mock_backtest:
                    with patch.object(selector.liquidity_scanner, 'print_scan_result'):
                        with patch.object(selector.multi_backtest, 'print_results'):
                            mock_scan.return_value = mock_coin_infos
                            mock_backtest.return_value = mock_backtest_scores

                            await selector.select_coins()

                            # 데이터 동기화가 호출되었는지 확인
                            mock_sync.assert_called_once()
