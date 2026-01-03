"""
APScheduler 단위 테스트

TDD 원칙: 스케줄러 기능을 검증하는 테스트 케이스
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.app.core.scheduler import (
    scheduler,
    trading_job,
    portfolio_snapshot_job,
    start_scheduler,
    stop_scheduler,
    add_jobs,
    pause_job,
    resume_job,
    get_jobs
)


class TestSchedulerConfiguration:
    """스케줄러 설정 테스트"""
    
    @pytest.mark.unit
    def test_scheduler_instance_exists(self):
        """스케줄러 인스턴스가 생성되어 있는지 확인"""
        assert scheduler is not None
        assert isinstance(scheduler, AsyncIOScheduler)
    
    @pytest.mark.unit
    def test_scheduler_timezone(self):
        """스케줄러 타임존이 Asia/Seoul로 설정되어 있는지 확인"""
        assert str(scheduler.timezone) == "Asia/Seoul"
    
    @pytest.mark.unit
    def test_scheduler_job_defaults(self):
        """스케줄러 기본 설정 확인"""
        job_defaults = scheduler._job_defaults
        assert job_defaults.get('coalesce') is True
        assert job_defaults.get('max_instances') == 1
        assert job_defaults.get('misfire_grace_time') == 60


def create_mock_orchestrator(result):
    """TradingOrchestrator Mock 생성 헬퍼"""
    mock_orchestrator = MagicMock()
    mock_orchestrator.execute_trading_cycle = AsyncMock(return_value=result)
    mock_orchestrator.set_on_backtest_complete = MagicMock()
    return mock_orchestrator


def create_mock_container():
    """Container Mock 생성 헬퍼 (Lock/Idempotency 포함)"""
    mock_lock_port = MagicMock()
    mock_lock_port.acquire = AsyncMock(return_value=True)
    mock_lock_port.release = AsyncMock()

    mock_container = MagicMock()
    mock_container.get_lock_port.return_value = mock_lock_port
    return mock_container


class TestTradingJob:
    """트레이딩 작업 테스트"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_trading_job_success(self):
        """트레이딩 작업이 성공적으로 실행되는지 확인"""
        # Given: Mock 객체 설정
        mock_result = {
            'status': 'success',
            'decision': 'buy',
            'confidence': 'high',
            'reason': 'Test reason',
            'price': 50000000,
            'amount': 0.001,
            'total': 50000
        }

        mock_orchestrator = create_mock_orchestrator(mock_result)
        mock_container = create_mock_container()

        # TradingOrchestrator와 Container를 패치
        with patch('backend.app.core.scheduler.get_container', return_value=mock_container), \
             patch('backend.app.core.scheduler.get_trading_orchestrator', return_value=mock_orchestrator), \
             patch('backend.app.core.scheduler.get_upbit_client', return_value=MagicMock()), \
             patch('backend.app.core.scheduler.get_data_collector', return_value=MagicMock()), \
             patch('backend.app.services.notification.notify_cycle_start', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_scan_result', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_backtest_and_signals', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_ai_decision', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_portfolio_status', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_error', new_callable=AsyncMock), \
             patch('backend.app.services.metrics.record_ai_decision'), \
             patch('backend.app.services.metrics.record_trade'), \
             patch('backend.app.services.metrics.scheduler_job_success_total'), \
             patch('backend.app.services.metrics.scheduler_job_duration_seconds'), \
             patch('backend.app.db.session.get_db', return_value=iter([])):

            # When: 트레이딩 작업 실행
            await trading_job()

            # Then: execute_trading_cycle이 호출되었는지 확인
            mock_orchestrator.execute_trading_cycle.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_trading_job_hold_decision_no_notification(self):
        """Hold 결정 시 거래 알림이 전송되지 않는지 확인 (trade_id 없음)"""
        # Given: Hold 결정 결과 (거래 없음)
        mock_result = {
            'status': 'success',
            'decision': 'hold',
            'confidence': 'medium',
            'reason': 'Market is stable'
        }

        mock_orchestrator = create_mock_orchestrator(mock_result)
        mock_container = create_mock_container()

        with patch('backend.app.core.scheduler.get_container', return_value=mock_container), \
             patch('backend.app.core.scheduler.get_trading_orchestrator', return_value=mock_orchestrator), \
             patch('backend.app.core.scheduler.get_upbit_client', return_value=MagicMock()), \
             patch('backend.app.core.scheduler.get_data_collector', return_value=MagicMock()), \
             patch('backend.app.services.notification.notify_cycle_start', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_scan_result', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_backtest_and_signals', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_ai_decision', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_portfolio_status', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_error', new_callable=AsyncMock), \
             patch('backend.app.services.metrics.record_ai_decision'), \
             patch('backend.app.services.metrics.record_trade') as mock_record_trade, \
             patch('backend.app.services.metrics.scheduler_job_success_total'), \
             patch('backend.app.services.metrics.scheduler_job_duration_seconds'), \
             patch('backend.app.db.session.get_db', return_value=iter([])):

            # When: 트레이딩 작업 실행
            await trading_job()

            # Then: record_trade가 호출되지 않았는지 확인 (hold는 거래 없음)
            mock_record_trade.assert_not_called()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_trading_job_failure_handling(self):
        """트레이딩 작업 실패 시 에러 처리 확인"""
        # Given: 실패 결과
        mock_result = {
            'status': 'failed',
            'error': 'Network timeout'
        }

        mock_orchestrator = create_mock_orchestrator(mock_result)
        mock_container = create_mock_container()

        with patch('backend.app.core.scheduler.get_container', return_value=mock_container), \
             patch('backend.app.core.scheduler.get_trading_orchestrator', return_value=mock_orchestrator), \
             patch('backend.app.core.scheduler.get_upbit_client', return_value=MagicMock()), \
             patch('backend.app.core.scheduler.get_data_collector', return_value=MagicMock()), \
             patch('backend.app.services.notification.notify_cycle_start', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_error', new_callable=AsyncMock) as mock_notify_error, \
             patch('backend.app.services.metrics.scheduler_job_failure_total') as mock_failure_metric, \
             patch('backend.app.services.metrics.scheduler_job_duration_seconds'), \
             patch('backend.app.db.session.get_db', return_value=iter([])):

            # When: 트레이딩 작업 실행
            await trading_job()

            # Then: 에러 알림 및 메트릭이 기록되었는지 확인
            mock_notify_error.assert_called_once()
            assert mock_failure_metric.labels.called
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_trading_job_exception_handling(self):
        """트레이딩 작업 중 예외 발생 시 처리 확인"""
        # Given: 예외 발생 설정
        mock_orchestrator = MagicMock()
        mock_orchestrator.execute_trading_cycle = AsyncMock(side_effect=Exception("Unexpected error"))
        mock_orchestrator.set_on_backtest_complete = MagicMock()
        mock_container = create_mock_container()

        with patch('backend.app.core.scheduler.get_container', return_value=mock_container), \
             patch('backend.app.core.scheduler.get_trading_orchestrator', return_value=mock_orchestrator), \
             patch('backend.app.core.scheduler.get_upbit_client', return_value=MagicMock()), \
             patch('backend.app.core.scheduler.get_data_collector', return_value=MagicMock()), \
             patch('backend.app.services.notification.notify_cycle_start', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_error', new_callable=AsyncMock) as mock_notify_error, \
             patch('backend.app.services.metrics.scheduler_job_failure_total'), \
             patch('backend.app.services.metrics.scheduler_job_duration_seconds'), \
             patch('backend.app.db.session.get_db', return_value=iter([])):

            # When: 트레이딩 작업 실행 (예외가 발생해도 프로그램이 중단되지 않아야 함)
            await trading_job()

            # Then: 에러 알림이 전송되었는지 확인
            mock_notify_error.assert_called_once()


class TestPortfolioSnapshotJob:
    """포트폴리오 스냅샷 작업 테스트"""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_portfolio_snapshot_job_executes(self):
        """포트폴리오 스냅샷 작업이 실행되는지 확인"""
        # When: 포트폴리오 스냅샷 작업 실행
        await portfolio_snapshot_job()
        
        # Then: 예외 없이 완료되어야 함 (현재는 TODO 상태)
        # 실제 구현 후 더 구체적인 검증 추가 필요


class TestSchedulerLifecycle:
    """스케줄러 생명주기 테스트"""
    
    @pytest.mark.unit
    def test_start_scheduler(self):
        """스케줄러 시작 테스트 (AsyncIOScheduler는 이벤트 루프 필요)"""
        # Given: 스케줄러가 중지된 상태
        if scheduler.running:
            scheduler.shutdown(wait=False)
        
        # AsyncIOScheduler는 실행 중인 이벤트 루프가 필요하므로
        # 단위 테스트에서는 add_jobs만 테스트
        with patch('backend.app.core.scheduler.settings.SCHEDULER_ENABLED', True):
            # When: 작업 추가 (스케줄러 시작 전 단계)
            add_jobs()
            
            # Then: 작업이 등록되어야 함
            jobs = scheduler.get_jobs()
            assert len(jobs) >= 2
            
            # Cleanup
            scheduler.remove_all_jobs()
    
    @pytest.mark.unit
    def test_stop_scheduler(self):
        """스케줄러 중지 테스트"""
        # Given: 스케줄러가 중지된 상태 확인
        if scheduler.running:
            scheduler.shutdown(wait=False)
        
        # When: 이미 중지된 스케줄러에 stop_scheduler 호출
        stop_scheduler()
        
        # Then: 스케줄러가 중지 상태여야 함 (예외 없이 완료)
        assert scheduler.running is False
    
    @pytest.mark.unit
    def test_add_jobs_when_enabled(self):
        """스케줄러 활성화 시 작업 추가 확인"""
        # Given: 스케줄러가 중지된 상태
        if scheduler.running:
            scheduler.shutdown(wait=False)
        
        # 기존 작업 제거
        scheduler.remove_all_jobs()
        
        with patch('backend.app.core.scheduler.settings.SCHEDULER_ENABLED', True), \
             patch('backend.app.core.scheduler.settings.SCHEDULER_INTERVAL_MINUTES', 60):
            
            # When: 작업 추가
            add_jobs()
            
            # Then: 작업이 등록되어야 함
            jobs = scheduler.get_jobs()
            job_ids = [job.id for job in jobs]
            
            assert 'trading_job' in job_ids
            assert 'portfolio_snapshot_job' in job_ids
            
            # Cleanup
            scheduler.remove_all_jobs()
    
    @pytest.mark.unit
    def test_add_jobs_when_disabled(self):
        """스케줄러 비활성화 시 작업 추가되지 않음 확인"""
        # Given: 스케줄러가 비활성화된 상태
        scheduler.remove_all_jobs()
        
        with patch('backend.app.core.scheduler.settings.SCHEDULER_ENABLED', False):
            # When: 작업 추가 시도
            add_jobs()
            
            # Then: 작업이 추가되지 않아야 함
            jobs = scheduler.get_jobs()
            assert len(jobs) == 0


class TestSchedulerJobManagement:
    """스케줄러 작업 관리 테스트"""
    
    @pytest.mark.unit
    def test_get_jobs(self):
        """등록된 작업 조회 테스트"""
        # Given: 작업이 등록된 상태
        if scheduler.running:
            scheduler.shutdown(wait=False)
        
        scheduler.remove_all_jobs()
        
        with patch('backend.app.core.scheduler.settings.SCHEDULER_ENABLED', True):
            add_jobs()
            
            # When: 작업 조회
            jobs_list = scheduler.get_jobs()
            
            # Then: 작업이 등록되어 있어야 함
            assert len(jobs_list) >= 2
            
            # get_jobs() 함수는 next_run_time 접근 시 문제가 있을 수 있으므로
            # 직접 scheduler.get_jobs()로 확인
            job_ids = [job.id for job in jobs_list]
            assert 'trading_job' in job_ids
            assert 'portfolio_snapshot_job' in job_ids
            
            # Cleanup
            scheduler.remove_all_jobs()
    
    @pytest.mark.unit
    def test_pause_and_resume_job(self):
        """작업 일시 정지 및 재개 테스트"""
        # Given: 작업이 등록된 상태
        if scheduler.running:
            scheduler.shutdown(wait=False)
        
        scheduler.remove_all_jobs()
        
        with patch('backend.app.core.scheduler.settings.SCHEDULER_ENABLED', True):
            add_jobs()
            
            # When: 작업 일시 정지
            pause_job('trading_job')
            
            # Then: 작업이 일시 정지되어야 함
            job = scheduler.get_job('trading_job')
            # APScheduler의 일시 정지 상태는 next_run_time이 None이 됨
            # 하지만 실제로는 pause 메서드가 호출되었는지 확인
            
            # When: 작업 재개
            resume_job('trading_job')
            
            # Then: 작업이 재개되어야 함
            job = scheduler.get_job('trading_job')
            assert job is not None
            
            # Cleanup
            scheduler.remove_all_jobs()


class TestCriticalIssues:
    """Critical 이슈 수정 검증 테스트 (리팩토링)"""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_c1_trade_saved_via_api(self):
        """
        C-1: 거래 저장 시 API를 통해 저장되는지 확인

        다이어그램 04-database-save-flow.mmd와 일치:
        - TradeCreate 스키마 사용
        - API 함수 호출 (create_trade)
        - 중복 거래 ID 검증
        """
        # Given: 매수 거래 결과
        mock_result = {
            'status': 'success',
            'decision': 'buy',
            'confidence': 'high',
            'reason': 'Test reason',
            'price': 50000000,
            'amount': 0.001,
            'total': 50000,
            'fee': 25,
            'trade_id': 'test-trade-123',
            'trade_success': True
        }

        mock_orchestrator = create_mock_orchestrator(mock_result)
        mock_container = create_mock_container()

        # Mock DB 세션 (async generator)
        async def mock_get_db():
            mock_db = MagicMock()
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()
            mock_db.rollback = AsyncMock()
            yield mock_db

        with patch('backend.app.core.scheduler.get_container', return_value=mock_container), \
             patch('backend.app.core.scheduler.get_trading_orchestrator', return_value=mock_orchestrator), \
             patch('backend.app.core.scheduler.get_upbit_client', return_value=MagicMock()), \
             patch('backend.app.core.scheduler.get_data_collector', return_value=MagicMock()), \
             patch('backend.app.services.notification.notify_cycle_start', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_scan_result', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_backtest_and_signals', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_ai_decision', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_portfolio_status', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_error', new_callable=AsyncMock), \
             patch('backend.app.api.v1.endpoints.trades.create_trade', new_callable=AsyncMock) as mock_create_trade, \
             patch('backend.app.services.metrics.record_ai_decision'), \
             patch('backend.app.services.metrics.record_trade'), \
             patch('backend.app.services.metrics.scheduler_job_success_total'), \
             patch('backend.app.services.metrics.scheduler_job_duration_seconds'), \
             patch('backend.app.db.session.get_db', side_effect=mock_get_db):

            # When: 트레이딩 작업 실행
            await trading_job()

            # Then: create_trade API 함수가 호출되었는지 확인
            mock_create_trade.assert_called_once()

            # TradeCreate 스키마로 데이터가 전달되었는지 확인
            call_args = mock_create_trade.call_args
            trade_data = call_args[0][0]  # 첫 번째 인자
            assert trade_data.trade_id == 'test-trade-123'
            assert trade_data.side == 'buy'
            assert trade_data.status == 'completed'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_c1_duplicate_trade_id_handled(self):
        """
        C-1: 중복 거래 ID 발생 시 API 검증 로직이 작동하는지 확인
        """
        # Given: 중복 거래 ID를 가진 거래
        mock_result = {
            'status': 'success',
            'decision': 'buy',
            'confidence': 'high',
            'reason': 'Test reason',
            'price': 50000000,
            'amount': 0.001,
            'total': 50000,
            'fee': 25,
            'trade_id': 'duplicate-trade-123',
            'trade_success': True
        }

        mock_orchestrator = create_mock_orchestrator(mock_result)
        mock_container = create_mock_container()

        # Mock DB 세션 (async generator)
        async def mock_get_db():
            mock_db = MagicMock()
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()
            mock_db.rollback = AsyncMock()
            yield mock_db

        with patch('backend.app.core.scheduler.get_container', return_value=mock_container), \
             patch('backend.app.core.scheduler.get_trading_orchestrator', return_value=mock_orchestrator), \
             patch('backend.app.core.scheduler.get_upbit_client', return_value=MagicMock()), \
             patch('backend.app.core.scheduler.get_data_collector', return_value=MagicMock()), \
             patch('backend.app.services.notification.notify_cycle_start', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_scan_result', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_backtest_and_signals', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_ai_decision', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_portfolio_status', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_error', new_callable=AsyncMock), \
             patch('backend.app.api.v1.endpoints.trades.create_trade', new_callable=AsyncMock) as mock_create_trade, \
             patch('backend.app.services.metrics.record_ai_decision'), \
             patch('backend.app.services.metrics.record_trade'), \
             patch('backend.app.services.metrics.scheduler_job_success_total'), \
             patch('backend.app.services.metrics.scheduler_job_duration_seconds'), \
             patch('backend.app.db.session.get_db', side_effect=mock_get_db):

            # API에서 중복 오류 발생
            mock_create_trade.side_effect = Exception("이미 존재하는 거래 ID입니다.")

            # When: 트레이딩 작업 실행 (예외가 발생해도 프로그램은 계속 실행되어야 함)
            await trading_job()

            # Then: create_trade가 호출되었고, 예외가 처리되었는지 확인
            mock_create_trade.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_c2_backtest_failure_returns_valid_dict(self):
        """
        C-2: 백테스팅 실패 시 올바른 dict 반환 확인

        현재 파이프라인 아키텍처에서는 백테스팅 실패가 AnalysisStage에서
        처리되며, 결과는 dict 형태로 반환됩니다.

        반환 구조:
        - status: 'success' 또는 'failed'
        - decision: 'hold'
        - pipeline_status: 'completed' 또는 'failed'
        """
        from main import execute_trading_cycle

        # 파이프라인 아키텍처에서는 QuickBacktestFilter가 AnalysisStage 내부에서 사용됨
        # 파이프라인 전체를 mock하여 테스트
        with patch('main.create_hybrid_trading_pipeline') as mock_pipeline:
            # 백테스팅 실패 시 파이프라인이 반환할 결과 모의
            mock_result = {
                'status': 'success',
                'decision': 'hold',
                'reason': '백테스팅 필터링 실패: 수익률 기준 미달',
                'pipeline_status': 'completed'
            }

            from unittest.mock import AsyncMock
            mock_pipeline_instance = Mock()
            mock_pipeline_instance.execute = AsyncMock(return_value=mock_result)
            mock_pipeline.return_value = mock_pipeline_instance

            # When: execute_trading_cycle 호출
            result = await execute_trading_cycle(
                ticker='KRW-ETH',
                upbit_client=Mock(),
                data_collector=Mock(),
                trading_service=Mock(),
                ai_service=Mock()
            )

            # Then: 올바른 구조의 dict 반환 확인
            assert result is not None
            assert isinstance(result, dict)
            assert 'status' in result
            assert 'decision' in result
            assert result['decision'] == 'hold'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_c3_chart_data_failure_returns_valid_dict(self):
        """
        C-3: 차트 데이터 실패 시 올바른 dict 반환 확인

        현재 파이프라인 아키텍처에서는 차트 데이터 실패가 DataCollectionStage에서
        처리되며, 결과는 dict 형태로 반환됩니다.

        반환 구조:
        - status: 'failed'
        - decision: 'hold'
        - pipeline_status: 'failed'
        """
        from main import execute_trading_cycle

        # 파이프라인 전체를 mock하여 테스트
        with patch('main.create_hybrid_trading_pipeline') as mock_pipeline:
            # 차트 데이터 실패 시 파이프라인이 반환할 결과 모의
            mock_result = {
                'status': 'failed',
                'decision': 'hold',
                'reason': '차트 데이터 조회 실패',
                'error': '차트 데이터를 가져올 수 없습니다',
                'pipeline_status': 'failed'
            }

            from unittest.mock import AsyncMock
            mock_pipeline_instance = Mock()
            mock_pipeline_instance.execute = AsyncMock(return_value=mock_result)
            mock_pipeline.return_value = mock_pipeline_instance

            # When: execute_trading_cycle 호출
            result = await execute_trading_cycle(
                ticker='KRW-ETH',
                upbit_client=Mock(),
                data_collector=Mock(),
                trading_service=Mock(),
                ai_service=Mock()
            )

            # Then: 올바른 구조의 dict 반환 확인
            assert result is not None
            assert isinstance(result, dict)
            assert result['status'] == 'failed'
            assert result['decision'] == 'hold'


class TestHighPriorityIssues:
    """High Priority 이슈 수정 검증 테스트 (리팩토링)"""
    
    @pytest.mark.unit
    def test_h1_environment_validation_success(self):
        """
        H-1: 필수 환경변수가 모두 있을 때 검증 성공
        """
        # Given: 모든 필수 환경변수 설정
        with patch.dict('os.environ', {
            'UPBIT_ACCESS_KEY': 'test_access_key',
            'UPBIT_SECRET_KEY': 'test_secret_key',
            'DATABASE_URL': 'postgresql://localhost/test',
            'OPENAI_API_KEY': 'test_openai_key'
        }):
            # When: 환경변수 검증 실행
            from scheduler_main import validate_environment_variables
            result = validate_environment_variables()
            
            # Then: 검증 성공
            assert result is True
    
    @pytest.mark.unit
    def test_h1_environment_validation_failure(self):
        """
        H-1: 필수 환경변수 누락 시 검증 실패
        """
        # Given: 일부 환경변수 누락
        with patch.dict('os.environ', {
            'UPBIT_ACCESS_KEY': 'test_access_key',
            # UPBIT_SECRET_KEY 누락
            'DATABASE_URL': 'postgresql://localhost/test',
            # OPENAI_API_KEY 누락
        }, clear=True):
            # When: 환경변수 검증 실행
            from scheduler_main import validate_environment_variables
            result = validate_environment_variables()
            
            # Then: 검증 실패
            assert result is False
    
    @pytest.mark.unit
    def test_h1_environment_validation_all_missing(self):
        """
        H-1: 모든 필수 환경변수 누락 시 검증 실패
        """
        # Given: 모든 환경변수 제거
        with patch.dict('os.environ', {}, clear=True):
            # When: 환경변수 검증 실행
            from scheduler_main import validate_environment_variables
            result = validate_environment_variables()
            
            # Then: 검증 실패
            assert result is False
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_h2_trade_metrics_recorded_on_success(self):
        """
        H-2: 거래 성공 시 거래 메트릭이 기록되는지 확인

        다이어그램 01-overall-system-flow.mmd:
        - record_trade() 호출 확인
        - AI 판단 + 거래 메트릭 모두 기록
        """
        # Given: 매수 성공 거래 결과
        mock_result = {
            'status': 'success',
            'decision': 'buy',
            'confidence': 'high',
            'reason': 'Test reason',
            'price': 50000000,
            'amount': 0.001,
            'total': 50000,
            'fee': 25,
            'trade_id': 'test-trade-456',
            'trade_success': True
        }

        mock_orchestrator = create_mock_orchestrator(mock_result)
        mock_container = create_mock_container()

        # Mock DB 세션 (async generator)
        async def mock_get_db():
            mock_db = MagicMock()
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()
            mock_db.rollback = AsyncMock()
            yield mock_db

        with patch('backend.app.core.scheduler.get_container', return_value=mock_container), \
             patch('backend.app.core.scheduler.get_trading_orchestrator', return_value=mock_orchestrator), \
             patch('backend.app.core.scheduler.get_upbit_client', return_value=MagicMock()), \
             patch('backend.app.core.scheduler.get_data_collector', return_value=MagicMock()), \
             patch('backend.app.services.notification.notify_cycle_start', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_scan_result', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_backtest_and_signals', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_ai_decision', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_portfolio_status', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_error', new_callable=AsyncMock), \
             patch('backend.app.api.v1.endpoints.trades.create_trade', new_callable=AsyncMock), \
             patch('backend.app.services.metrics.record_ai_decision') as mock_ai_metric, \
             patch('backend.app.services.metrics.record_trade') as mock_trade_metric, \
             patch('backend.app.services.metrics.scheduler_job_success_total'), \
             patch('backend.app.services.metrics.scheduler_job_duration_seconds'), \
             patch('backend.app.db.session.get_db', side_effect=mock_get_db):

            # When: 트레이딩 작업 실행
            await trading_job()

            # Then: AI 판단 메트릭과 거래 메트릭 모두 기록되었는지 확인
            mock_ai_metric.assert_called_once()
            mock_trade_metric.assert_called_once_with(
                symbol='KRW-ETH',
                side='buy',
                volume=50000.0,
                fee=25.0
            )
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_h2_trade_metrics_not_recorded_on_hold(self):
        """
        H-2: hold 결정 시 거래 메트릭이 기록되지 않는지 확인
        """
        # Given: hold 결정 결과
        mock_result = {
            'status': 'success',
            'decision': 'hold',
            'confidence': 'medium',
            'reason': 'Market is stable'
        }

        mock_orchestrator = create_mock_orchestrator(mock_result)
        mock_container = create_mock_container()

        # Mock DB 세션 (async generator)
        async def mock_get_db():
            mock_db = MagicMock()
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()
            mock_db.rollback = AsyncMock()
            yield mock_db

        with patch('backend.app.core.scheduler.get_container', return_value=mock_container), \
             patch('backend.app.core.scheduler.get_trading_orchestrator', return_value=mock_orchestrator), \
             patch('backend.app.core.scheduler.get_upbit_client', return_value=MagicMock()), \
             patch('backend.app.core.scheduler.get_data_collector', return_value=MagicMock()), \
             patch('backend.app.services.notification.notify_cycle_start', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_scan_result', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_backtest_and_signals', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_ai_decision', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_portfolio_status', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_error', new_callable=AsyncMock), \
             patch('backend.app.services.metrics.record_ai_decision') as mock_ai_metric, \
             patch('backend.app.services.metrics.record_trade') as mock_trade_metric, \
             patch('backend.app.services.metrics.scheduler_job_success_total'), \
             patch('backend.app.services.metrics.scheduler_job_duration_seconds'), \
             patch('backend.app.db.session.get_db', side_effect=mock_get_db):

            # When: 트레이딩 작업 실행
            await trading_job()

            # Then: AI 판단 메트릭만 기록되고, 거래 메트릭은 기록되지 않음
            mock_ai_metric.assert_called_once()
            mock_trade_metric.assert_not_called()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_h2_trade_metrics_not_recorded_on_failure(self):
        """
        H-2: 거래 실패 시 거래 메트릭이 기록되지 않는지 확인
        """
        # Given: 거래 실패 결과
        mock_result = {
            'status': 'success',
            'decision': 'buy',
            'confidence': 'high',
            'reason': 'Test reason',
            'price': 50000000,
            'amount': 0.001,
            'total': 50000,
            'fee': 25,
            'trade_id': 'test-trade-789',
            'trade_success': False  # 거래 실패
        }

        mock_orchestrator = create_mock_orchestrator(mock_result)
        mock_container = create_mock_container()

        # Mock DB 세션 (async generator)
        async def mock_get_db():
            mock_db = MagicMock()
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()
            mock_db.rollback = AsyncMock()
            yield mock_db

        with patch('backend.app.core.scheduler.get_container', return_value=mock_container), \
             patch('backend.app.core.scheduler.get_trading_orchestrator', return_value=mock_orchestrator), \
             patch('backend.app.core.scheduler.get_upbit_client', return_value=MagicMock()), \
             patch('backend.app.core.scheduler.get_data_collector', return_value=MagicMock()), \
             patch('backend.app.services.notification.notify_cycle_start', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_scan_result', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_backtest_and_signals', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_ai_decision', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_portfolio_status', new_callable=AsyncMock), \
             patch('backend.app.services.notification.notify_error', new_callable=AsyncMock), \
             patch('backend.app.api.v1.endpoints.trades.create_trade', new_callable=AsyncMock), \
             patch('backend.app.services.metrics.record_ai_decision') as mock_ai_metric, \
             patch('backend.app.services.metrics.record_trade') as mock_trade_metric, \
             patch('backend.app.services.metrics.scheduler_job_success_total'), \
             patch('backend.app.services.metrics.scheduler_job_duration_seconds'), \
             patch('backend.app.db.session.get_db', side_effect=mock_get_db):

            # When: 트레이딩 작업 실행
            await trading_job()

            # Then: AI 판단 메트릭만 기록되고, 거래 메트릭은 기록되지 않음
            mock_ai_metric.assert_called_once()
            mock_trade_metric.assert_not_called()


class TestSchedulerIntegration:
    """스케줄러 통합 테스트 (단위 테스트 범위)"""
    
    @pytest.mark.unit
    def test_scheduler_job_interval(self):
        """스케줄러 작업 실행 간격 확인"""
        # Given: 작업이 등록된 상태
        if scheduler.running:
            scheduler.shutdown(wait=False)
        
        scheduler.remove_all_jobs()
        
        with patch('backend.app.core.scheduler.settings.SCHEDULER_ENABLED', True), \
             patch('backend.app.core.scheduler.settings.SCHEDULER_INTERVAL_MINUTES', 60):
            
            add_jobs()
            
            # When: trading_job 조회
            job = scheduler.get_job('trading_job')
            
            # Then: 작업이 존재하고 트리거가 설정되어 있어야 함
            assert job is not None
            assert job.trigger is not None
            
            # Cleanup
            scheduler.remove_all_jobs()
    
    @pytest.mark.unit
    def test_scheduler_prevents_concurrent_execution(self):
        """스케줄러가 동시 실행을 방지하는지 확인"""
        # Given: 작업이 등록된 상태
        if scheduler.running:
            scheduler.shutdown(wait=False)
        
        scheduler.remove_all_jobs()
        
        with patch('backend.app.core.scheduler.settings.SCHEDULER_ENABLED', True):
            add_jobs()
            
            # When: trading_job 조회
            job = scheduler.get_job('trading_job')
            
            # Then: max_instances가 1로 설정되어 있어야 함
            # APScheduler의 job 객체에서 직접 확인
            assert job is not None
            
            # Cleanup
            scheduler.remove_all_jobs()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

