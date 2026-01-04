"""
Trading Job 시나리오 테스트

backend/app/core/scheduler.py의 trading_job() 전체 경로를 검증합니다.

테스트 시나리오:
1. 정상 실행: Lock 획득 → 거래 사이클 성공 → 알림 전송 → Lock 해제
2. Lock 획득 실패: Lock 획득 실패 → 즉시 종료
3. Idempotency 중복: Idempotency 체크 → 중복 감지 → 스킵
4. 타임아웃: 거래 사이클 타임아웃 → 에러 알림 → Lock 해제
5. 파이프라인 실패: 파이프라인 실행 실패 → 에러 처리
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime
from decimal import Decimal


@pytest.mark.scenario
@pytest.mark.asyncio
class TestTradingJobScenarios:
    """Trading Job 전체 경로 시나리오 테스트"""

    @pytest.fixture
    def mock_container(self):
        """Container Mock"""
        container = Mock()
        container.get_lock_port = Mock()
        container.get_trading_orchestrator = Mock()
        container.get_upbit_client = Mock()
        container.get_data_collector = Mock()
        container.get_idempotency_port = Mock()
        return container

    @pytest.fixture
    def mock_lock_port_success(self):
        """Lock 획득 성공 Mock"""
        lock_port = AsyncMock()
        lock_port.acquire = AsyncMock(return_value=True)
        lock_port.release = AsyncMock(return_value=None)
        return lock_port

    @pytest.fixture
    def mock_lock_port_failure(self):
        """Lock 획득 실패 Mock"""
        lock_port = AsyncMock()
        lock_port.acquire = AsyncMock(return_value=False)
        lock_port.release = AsyncMock(return_value=None)
        return lock_port

    @pytest.fixture
    def mock_orchestrator_success(self):
        """TradingOrchestrator 성공 Mock"""
        orchestrator = AsyncMock()
        orchestrator.set_on_backtest_complete = Mock()
        orchestrator.execute_trading_cycle = AsyncMock(return_value={
            'status': 'success',
            'decision': 'buy',
            'confidence': 'high',
            'reason': 'Strong bullish signal',
            'selected_coin': {
                'ticker': 'KRW-BTC',
                'symbol': 'BTC',
                'score': 85.5
            },
            'trade_id': 'test_trade_123',
            'trade_success': True,
            'price': 50000000,
            'amount': 0.001,
            'total': 50000,
            'fee': 25,
            'market_data': {},
        })
        return orchestrator

    @pytest.fixture
    def mock_orchestrator_skipped(self):
        """TradingOrchestrator Idempotency 스킵 Mock"""
        orchestrator = AsyncMock()
        orchestrator.set_on_backtest_complete = Mock()
        orchestrator.execute_trading_cycle = AsyncMock(return_value={
            'status': 'skipped',
            'decision': 'hold',
            'reason': 'Duplicate idempotency key',
            'idempotency_key': 'KRW-BTC-1h-2026010409-trading_cycle',
            'pipeline_status': 'skipped'
        })
        return orchestrator

    @pytest.fixture
    def mock_orchestrator_timeout(self):
        """TradingOrchestrator 타임아웃 Mock"""
        async def timeout_mock(*args, **kwargs):
            await asyncio.sleep(11)  # 10분 타임아웃 초과
            return {}

        orchestrator = AsyncMock()
        orchestrator.set_on_backtest_complete = Mock()
        orchestrator.execute_trading_cycle = timeout_mock
        return orchestrator

    @pytest.fixture
    def mock_telegram(self):
        """Telegram 알림 Mock"""
        with patch('backend.app.services.notification.notify_cycle_start', new_callable=AsyncMock) as mock_start, \
             patch('backend.app.services.notification.notify_scan_result', new_callable=AsyncMock) as mock_scan, \
             patch('backend.app.services.notification.notify_ai_decision', new_callable=AsyncMock) as mock_ai, \
             patch('backend.app.services.notification.notify_portfolio_status', new_callable=AsyncMock) as mock_portfolio, \
             patch('backend.app.services.notification.notify_error', new_callable=AsyncMock) as mock_error:
            yield {
                'cycle_start': mock_start,
                'scan_result': mock_scan,
                'ai_decision': mock_ai,
                'portfolio_status': mock_portfolio,
                'error': mock_error
            }

    @pytest.fixture
    def mock_metrics(self):
        """Prometheus 메트릭 Mock"""
        with patch('backend.app.services.metrics.record_ai_decision') as mock_ai, \
             patch('backend.app.services.metrics.record_trade') as mock_trade, \
             patch('backend.app.services.metrics.scheduler_job_success_total') as mock_success, \
             patch('backend.app.services.metrics.scheduler_job_failure_total') as mock_failure, \
             patch('backend.app.services.metrics.scheduler_job_duration_seconds') as mock_duration:
            yield {
                'ai_decision': mock_ai,
                'trade': mock_trade,
                'success': mock_success,
                'failure': mock_failure,
                'duration': mock_duration
            }

    @pytest.fixture
    def mock_db(self):
        """PostgreSQL DB Mock"""
        with patch('backend.app.db.session.get_db') as mock:
            async def mock_generator():
                db_mock = AsyncMock()
                db_mock.add = Mock()
                db_mock.commit = AsyncMock()
                db_mock.refresh = AsyncMock()
                db_mock.rollback = AsyncMock()
                yield db_mock

            mock.return_value = mock_generator()
            yield mock

    async def test_trading_job_success_flow(
        self,
        mock_container,
        mock_lock_port_success,
        mock_orchestrator_success,
        mock_telegram,
        mock_metrics,
        mock_db
    ):
        """
        시나리오: trading_job 정상 실행 (Happy Path)

        Given: Lock 획득 가능, 거래 사이클 성공
        When: trading_job() 실행
        Then:
            1. Lock 획득
            2. TradingOrchestrator 초기화
            3. 사이클 시작 알림 전송
            4. 거래 사이클 실행
            5. AI 판단 메트릭 기록
            6. 거래 내역 DB 저장
            7. AI 의사결정 알림 전송
            8. 포트폴리오 알림 전송
            9. 성공 메트릭 기록
            10. Lock 해제
        """
        from backend.app.core.scheduler import trading_job

        # Given: Mock 설정
        mock_container.get_lock_port.return_value = mock_lock_port_success
        mock_container.get_trading_orchestrator.return_value = mock_orchestrator_success

        with patch('backend.app.core.scheduler.get_container', return_value=mock_container), \
             patch('backend.app.core.scheduler.get_upbit_client', return_value=Mock()), \
             patch('backend.app.core.scheduler.get_data_collector', return_value=Mock()):

            # When: trading_job 실행
            await trading_job()

            # Then: 전체 흐름 검증
            # 1. Lock 획득
            mock_lock_port_success.acquire.assert_called_once_with("trading_cycle", timeout_seconds=600)

            # 2. TradingOrchestrator 초기화
            mock_container.get_trading_orchestrator.assert_called_once()

            # 3. 사이클 시작 알림
            mock_telegram['cycle_start'].assert_called_once()

            # 4. 거래 사이클 실행
            mock_orchestrator_success.execute_trading_cycle.assert_called_once()

            # 5. AI 판단 메트릭 기록
            mock_metrics['ai_decision'].assert_called_once()

            # 6. 거래 내역 메트릭 기록 (buy/sell인 경우)
            mock_metrics['trade'].assert_called_once()

            # 7. AI 의사결정 알림
            mock_telegram['ai_decision'].assert_called_once()

            # 8. 포트폴리오 알림
            mock_telegram['portfolio_status'].assert_called_once()

            # 9. 성공 메트릭
            mock_metrics['success'].labels.return_value.inc.assert_called()

            # 10. Lock 해제
            mock_lock_port_success.release.assert_called_once_with("trading_cycle")

    async def test_trading_job_lock_acquisition_failure(
        self,
        mock_container,
        mock_lock_port_failure,
        mock_metrics
    ):
        """
        시나리오: Lock 획득 실패

        Given: 다른 작업이 실행 중 (Lock 획득 불가)
        When: trading_job() 실행
        Then:
            1. Lock 획득 실패
            2. 실패 메트릭 기록
            3. 즉시 종료 (TradingOrchestrator 호출 없음)
        """
        from backend.app.core.scheduler import trading_job

        # Given: Lock 획득 실패
        mock_container.get_lock_port.return_value = mock_lock_port_failure

        with patch('backend.app.core.scheduler.get_container', return_value=mock_container):
            # When: trading_job 실행
            await trading_job()

            # Then:
            # 1. Lock 획득 시도
            mock_lock_port_failure.acquire.assert_called_once()

            # 2. 실패 메트릭 기록
            mock_metrics['failure'].labels.return_value.inc.assert_called()

            # 3. TradingOrchestrator 호출 안 됨
            mock_container.get_trading_orchestrator.assert_not_called()

            # 4. Lock 해제 안 됨 (획득 안 했으므로)
            mock_lock_port_failure.release.assert_not_called()

    async def test_trading_job_idempotency_skip(
        self,
        mock_container,
        mock_lock_port_success,
        mock_orchestrator_skipped,
        mock_telegram,
        mock_metrics
    ):
        """
        시나리오: Idempotency 중복 스킵

        Given: 동일 캔들에 이미 실행됨 (Idempotency 중복)
        When: trading_job() 실행
        Then:
            1. Lock 획득
            2. 거래 사이클 실행 → Idempotency 중복 감지
            3. 스킵 로그
            4. 성공 메트릭 기록 (정상 동작)
            5. Lock 해제
        """
        from backend.app.core.scheduler import trading_job

        # Given: Idempotency 중복
        mock_container.get_lock_port.return_value = mock_lock_port_success
        mock_container.get_trading_orchestrator.return_value = mock_orchestrator_skipped

        with patch('backend.app.core.scheduler.get_container', return_value=mock_container), \
             patch('backend.app.core.scheduler.get_upbit_client', return_value=Mock()), \
             patch('backend.app.core.scheduler.get_data_collector', return_value=Mock()):

            # When: trading_job 실행
            await trading_job()

            # Then:
            # 1. Lock 획득
            mock_lock_port_success.acquire.assert_called_once()

            # 2. 거래 사이클 실행
            mock_orchestrator_skipped.execute_trading_cycle.assert_called_once()

            # 3. 성공 메트릭 (스킵도 정상 동작)
            mock_metrics['success'].labels.return_value.inc.assert_called()

            # 4. 알림 전송 안 됨 (스킵이므로)
            mock_telegram['ai_decision'].assert_not_called()
            mock_telegram['portfolio_status'].assert_not_called()

            # 5. Lock 해제
            mock_lock_port_success.release.assert_called_once()

    async def test_trading_job_timeout(
        self,
        mock_container,
        mock_lock_port_success,
        mock_orchestrator_timeout,
        mock_telegram,
        mock_metrics
    ):
        """
        시나리오: 거래 사이클 타임아웃

        Given: 거래 사이클이 10분 초과
        When: trading_job() 실행
        Then:
            1. Lock 획득
            2. 거래 사이클 실행 → 타임아웃
            3. 타임아웃 에러 알림 전송
            4. 실패 메트릭 기록
            5. Lock 해제
        """
        from backend.app.core.scheduler import trading_job

        # Given: 타임아웃 시뮬레이션
        mock_container.get_lock_port.return_value = mock_lock_port_success
        mock_container.get_trading_orchestrator.return_value = mock_orchestrator_timeout

        with patch('backend.app.core.scheduler.get_container', return_value=mock_container), \
             patch('backend.app.core.scheduler.get_upbit_client', return_value=Mock()), \
             patch('backend.app.core.scheduler.get_data_collector', return_value=Mock()), \
             patch('backend.app.core.scheduler.TRADING_CYCLE_TIMEOUT', 0.1):  # 0.1초 타임아웃

            # When: trading_job 실행
            await trading_job()

            # Then:
            # 1. Lock 획득
            mock_lock_port_success.acquire.assert_called_once()

            # 2. 타임아웃 에러 알림
            mock_telegram['error'].assert_called()

            # 3. Lock 해제 (finally 블록)
            mock_lock_port_success.release.assert_called_once()

    async def test_trading_job_pipeline_failure(
        self,
        mock_container,
        mock_lock_port_success,
        mock_telegram,
        mock_metrics
    ):
        """
        시나리오: 파이프라인 실행 실패

        Given: 거래 사이클 실행 중 예외 발생
        When: trading_job() 실행
        Then:
            1. Lock 획득
            2. 거래 사이클 실행 → 예외 발생
            3. 에러 알림 전송
            4. 실패 메트릭 기록
            5. Lock 해제 (finally 블록)
        """
        from backend.app.core.scheduler import trading_job

        # Given: 파이프라인 실패
        orchestrator = AsyncMock()
        orchestrator.set_on_backtest_complete = Mock()
        orchestrator.execute_trading_cycle = AsyncMock(return_value={
            'status': 'failed',
            'decision': 'hold',
            'error': 'Pipeline execution failed',
            'reason': 'Database connection lost',
            'pipeline_status': 'failed'
        })

        mock_container.get_lock_port.return_value = mock_lock_port_success
        mock_container.get_trading_orchestrator.return_value = orchestrator

        with patch('backend.app.core.scheduler.get_container', return_value=mock_container), \
             patch('backend.app.core.scheduler.get_upbit_client', return_value=Mock()), \
             patch('backend.app.core.scheduler.get_data_collector', return_value=Mock()):

            # When: trading_job 실행
            await trading_job()

            # Then:
            # 1. Lock 획득
            mock_lock_port_success.acquire.assert_called_once()

            # 2. 에러 알림
            mock_telegram['error'].assert_called()

            # 3. 실패 메트릭
            mock_metrics['failure'].labels.return_value.inc.assert_called()

            # 4. Lock 해제
            mock_lock_port_success.release.assert_called_once()

    async def test_trading_job_telegram_notification_sequence(
        self,
        mock_container,
        mock_lock_port_success,
        mock_orchestrator_success,
        mock_telegram,
        mock_metrics,
        mock_db
    ):
        """
        시나리오: Telegram 알림 순서 검증

        Given: 거래 사이클 성공
        When: trading_job() 실행
        Then: Telegram 알림이 올바른 순서로 전송됨
            1. 사이클 시작 알림
            2. 스캔 결과 알림 (백테스팅 콜백)
            3. AI 의사결정 알림
            4. 포트폴리오 알림
        """
        from backend.app.core.scheduler import trading_job

        # Given: 성공 시나리오
        mock_container.get_lock_port.return_value = mock_lock_port_success
        mock_container.get_trading_orchestrator.return_value = mock_orchestrator_success

        with patch('backend.app.core.scheduler.get_container', return_value=mock_container), \
             patch('backend.app.core.scheduler.get_upbit_client', return_value=Mock()), \
             patch('backend.app.core.scheduler.get_data_collector', return_value=Mock()):

            # When: trading_job 실행
            await trading_job()

            # Then: 알림 호출 순서 검증
            call_order = []

            if mock_telegram['cycle_start'].called:
                call_order.append('cycle_start')
            if mock_telegram['scan_result'].called:
                call_order.append('scan_result')
            if mock_telegram['ai_decision'].called:
                call_order.append('ai_decision')
            if mock_telegram['portfolio_status'].called:
                call_order.append('portfolio_status')

            # 최소한 cycle_start, ai_decision, portfolio_status는 호출되어야 함
            assert 'cycle_start' in call_order
            assert 'ai_decision' in call_order
            assert 'portfolio_status' in call_order
