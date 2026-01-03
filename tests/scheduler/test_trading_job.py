"""
트레이딩 작업 테스트

trading_job의 실행, 성공, 실패 케이스 테스트
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from backend.app.core.scheduler import trading_job
from .conftest import create_mock_orchestrator, create_mock_container, create_mock_db


class TestTradingJobExecution:
    """트레이딩 작업 실행 테스트"""

    @pytest.mark.scheduler
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_trading_job_success(self, mock_success_result):
        """트레이딩 작업이 성공적으로 실행되는지 확인"""
        mock_orchestrator = create_mock_orchestrator(mock_success_result)
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
             patch('backend.app.services.metrics.record_trade'), \
             patch('backend.app.services.metrics.scheduler_job_success_total'), \
             patch('backend.app.services.metrics.scheduler_job_duration_seconds'), \
             patch('backend.app.db.session.get_db', return_value=iter([])):

            await trading_job()
            mock_orchestrator.execute_trading_cycle.assert_called_once()

    @pytest.mark.scheduler
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_trading_job_hold_no_trade(self, mock_hold_result):
        """Hold 결정 시 거래 메트릭이 기록되지 않는지 확인"""
        mock_orchestrator = create_mock_orchestrator(mock_hold_result)
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

            await trading_job()
            mock_record_trade.assert_not_called()


class TestTradingJobErrorHandling:
    """트레이딩 작업 에러 처리 테스트"""

    @pytest.mark.scheduler
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_trading_job_failure_handling(self, mock_failure_result):
        """트레이딩 작업 실패 시 에러 처리 확인"""
        mock_orchestrator = create_mock_orchestrator(mock_failure_result)
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

            await trading_job()
            mock_notify_error.assert_called_once()
            assert mock_failure_metric.labels.called

    @pytest.mark.scheduler
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_trading_job_exception_handling(self):
        """트레이딩 작업 중 예외 발생 시 처리 확인"""
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

            # 예외가 발생해도 프로그램이 중단되지 않아야 함
            await trading_job()
            mock_notify_error.assert_called_once()
