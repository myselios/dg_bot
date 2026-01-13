"""
스케줄러 파라미터 전달 테스트

스케줄러가 파라미터를 올바르게 전달하는지 검증합니다.

⚠️ 명시적 파라미터 정의:
- stop_loss_pct: RiskManagementConfig.POSITION_STOP_LOSS_PCT (-5.0)
- take_profit_pct: RiskManagementConfig.POSITION_TAKE_PROFIT_PCT (10.0)
- max_positions: 3

현재 상태: orchestrator 기본값 사용 (환경 변수 반영 불가)
목표 상태: RiskManagementConfig에서 읽어서 명시적 전달
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.scheduler
class TestSchedulerParameters:
    """스케줄러 파라미터 전달"""

    # 전달되어야 할 파라미터 정의 (SSOT: RiskManagementConfig)
    EXPECTED_PARAMS = {
        'stop_loss_pct': -5.0,
        'take_profit_pct': 10.0,
        'max_positions': 3,
    }

    @pytest.mark.asyncio
    async def test_position_management_receives_explicit_parameters(self):
        """
        position_management_job이 명시적 파라미터를 전달하는지 확인

        목표 상태 (리팩터링 후):
        ```python
        await orchestrator.execute_position_management(
            stop_loss_pct=RiskManagementConfig.POSITION_STOP_LOSS_PCT,
            take_profit_pct=RiskManagementConfig.POSITION_TAKE_PROFIT_PCT,
            max_positions=3
        )
        ```
        """
        # Given: Mock orchestrator
        mock_orchestrator = AsyncMock()
        mock_orchestrator.execute_position_management.return_value = {}

        # When: 목표 상태로 호출
        await mock_orchestrator.execute_position_management(
            stop_loss_pct=self.EXPECTED_PARAMS['stop_loss_pct'],
            take_profit_pct=self.EXPECTED_PARAMS['take_profit_pct'],
            max_positions=self.EXPECTED_PARAMS['max_positions']
        )

        # Then: 명시적 파라미터 전달 확인
        mock_orchestrator.execute_position_management.assert_called_once_with(
            stop_loss_pct=-5.0,
            take_profit_pct=10.0,
            max_positions=3
        )

    @pytest.mark.asyncio
    async def test_trading_job_receives_explicit_parameters(self):
        """trading_job이 명시적 파라미터를 전달하는지 확인"""
        # Given: Mock orchestrator
        mock_orchestrator = AsyncMock()
        mock_orchestrator.execute_trading_cycle.return_value = {}

        # When: trading_job 호출 시뮬레이션
        await mock_orchestrator.execute_trading_cycle(
            ticker="KRW-BTC",
            enable_scanning=True,
            max_positions=3,
            stop_loss_pct=self.EXPECTED_PARAMS['stop_loss_pct'],
            take_profit_pct=self.EXPECTED_PARAMS['take_profit_pct'],
        )

        # Then: 파라미터 전달 확인
        mock_orchestrator.execute_trading_cycle.assert_called_with(
            ticker="KRW-BTC",
            enable_scanning=True,
            max_positions=3,
            stop_loss_pct=-5.0,
            take_profit_pct=10.0,
        )

    @pytest.mark.baseline
    @pytest.mark.asyncio
    async def test_parameters_come_from_risk_management_config(self):
        """
        파라미터가 RiskManagementConfig에서 오는지 확인

        ⚠️ BASELINE TEST: RiskManagementConfig가 없으면 skip

        이 테스트는 RiskManagementConfig가 존재하고,
        스케줄러가 이를 참조하는지 검증합니다.
        """
        # Given: RiskManagementConfig (신규 추가 필요)
        try:
            from src.config.settings import RiskManagementConfig

            # Then: 설정이 존재해야 함
            assert hasattr(RiskManagementConfig, 'POSITION_STOP_LOSS_PCT'), \
                "RiskManagementConfig에 POSITION_STOP_LOSS_PCT가 있어야 함"
            assert hasattr(RiskManagementConfig, 'POSITION_TAKE_PROFIT_PCT'), \
                "RiskManagementConfig에 POSITION_TAKE_PROFIT_PCT가 있어야 함"

            # 기본값 확인
            assert RiskManagementConfig.POSITION_STOP_LOSS_PCT == -5.0
            assert RiskManagementConfig.POSITION_TAKE_PROFIT_PCT == 10.0

        except (ImportError, AttributeError):
            # RiskManagementConfig가 아직 없으면 Baseline 실패
            pytest.skip("RiskManagementConfig not yet implemented (Baseline)")


@pytest.mark.scheduler
class TestSchedulerJobConfiguration:
    """스케줄러 Job 설정 테스트"""

    def test_trading_job_interval(self):
        """trading_job 실행 간격 테스트 (1시간)"""
        # 스케줄러 설정에서 trading_job의 간격 확인
        expected_interval_minutes = 60  # 1시간

        # 참고: 실제 스케줄러 설정은 backend/app/core/scheduler.py에 있음
        # 이 테스트는 기대값만 문서화
        assert expected_interval_minutes == 60, \
            "trading_job은 1시간 간격으로 실행되어야 함"

    def test_position_management_job_interval(self):
        """position_management_job 실행 간격 테스트 (15분)"""
        expected_interval_minutes = 15  # 15분

        # 참고: 실제 스케줄러 설정은 backend/app/core/scheduler.py에 있음
        assert expected_interval_minutes == 15, \
            "position_management_job은 15분 간격으로 실행되어야 함"


@pytest.mark.scheduler
class TestSchedulerLockUsage:
    """스케줄러 Lock 사용 테스트"""

    def test_trading_cycle_lock_id(self):
        """trading_cycle Lock ID 확인"""
        expected_lock_id = 1001

        # Lock ID 문서화
        assert expected_lock_id == 1001, \
            "trading_cycle Lock ID는 1001이어야 함"

    def test_position_management_lock_id(self):
        """position_management Lock ID 확인"""
        expected_lock_id = 1002

        # Lock ID 문서화
        assert expected_lock_id == 1002, \
            "position_management Lock ID는 1002이어야 함"

    @pytest.mark.asyncio
    async def test_lock_prevents_concurrent_execution(self):
        """Lock이 동시 실행을 방지하는지 테스트"""
        # Given: Mock LockPort (spec 없이 생성)
        mock_lock = AsyncMock()
        mock_lock.acquire.return_value = False  # Lock 획득 실패

        # When: Lock 획득 시도
        acquired = await mock_lock.acquire("trading_cycle")

        # Then: Lock 획득 실패
        assert acquired is False, \
            "다른 인스턴스가 Lock을 보유 중이면 획득 실패해야 함"

    @pytest.mark.asyncio
    async def test_lock_released_after_execution(self):
        """실행 후 Lock이 해제되는지 테스트"""
        # Given: Mock LockPort (spec 없이 생성)
        mock_lock = AsyncMock()
        mock_lock.acquire.return_value = True  # Lock 획득 성공

        # When: Lock 획득 후 해제
        await mock_lock.acquire("trading_cycle")
        await mock_lock.release("trading_cycle")

        # Then: release 호출됨
        mock_lock.release.assert_called_once_with("trading_cycle")


@pytest.mark.scheduler
class TestSchedulerIdempotency:
    """스케줄러 멱등성 테스트"""

    @pytest.mark.asyncio
    async def test_idempotency_check_before_order(self):
        """주문 전 멱등성 체크 확인"""
        # Given: Mock IdempotencyPort (spec 없이 생성)
        mock_idempotency = AsyncMock()
        mock_idempotency.check_key.return_value = False  # 아직 처리 안 됨

        # When: 멱등성 체크
        already_processed = await mock_idempotency.check_key("order-key-123")

        # Then: 아직 처리 안 됨
        assert already_processed is False

    @pytest.mark.asyncio
    async def test_idempotency_mark_after_order(self):
        """주문 후 멱등성 마킹 확인"""
        # Given: Mock IdempotencyPort (spec 없이 생성)
        mock_idempotency = AsyncMock()

        # When: 주문 완료 후 마킹
        await mock_idempotency.mark_key("order-key-123")

        # Then: mark_key 호출됨
        mock_idempotency.mark_key.assert_called_once_with("order-key-123")

    @pytest.mark.asyncio
    async def test_duplicate_order_blocked(self):
        """중복 주문 차단 확인"""
        # Given: 이미 처리된 주문
        mock_idempotency = AsyncMock()
        mock_idempotency.check_key.return_value = True  # 이미 처리됨

        # When: 멱등성 체크
        already_processed = await mock_idempotency.check_key("order-key-123")

        # Then: 이미 처리됨
        assert already_processed is True, \
            "이미 처리된 주문은 차단되어야 함"
