"""
Tests for RiskState model and RiskStateRepository - TDD Phase 2

RED Phase: 이 테스트들은 RiskState/RiskStateRepository 구현 전에 모두 실패해야 합니다.
"""
import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch


class TestRiskStateModelExists:
    """RiskState SQLAlchemy 모델 존재 테스트"""

    def test_risk_state_model_exists(self):
        """RiskState 모델이 존재해야 함"""
        from backend.app.models.risk_state import RiskState
        assert RiskState is not None

    def test_risk_state_has_required_columns(self):
        """RiskState 모델에 필수 컬럼이 있어야 함"""
        from backend.app.models.risk_state import RiskState

        # 필수 컬럼 확인
        assert hasattr(RiskState, 'id')
        assert hasattr(RiskState, 'state_date')
        assert hasattr(RiskState, 'daily_pnl')
        assert hasattr(RiskState, 'daily_trade_count')
        assert hasattr(RiskState, 'weekly_pnl')
        assert hasattr(RiskState, 'safe_mode')
        assert hasattr(RiskState, 'safe_mode_reason')
        assert hasattr(RiskState, 'last_trade_time')
        assert hasattr(RiskState, 'created_at')
        assert hasattr(RiskState, 'updated_at')

    def test_risk_state_in_models_init(self):
        """RiskState가 models/__init__.py에 등록되어 있어야 함"""
        from backend.app.models import RiskState
        assert RiskState is not None


class TestRiskStateSchemaExists:
    """RiskState Pydantic 스키마 테스트"""

    def test_risk_state_schema_exists(self):
        """RiskStateSchema가 존재해야 함"""
        from backend.app.schemas.risk_state import RiskStateCreate, RiskStateRead
        assert RiskStateCreate is not None
        assert RiskStateRead is not None


class TestRiskStateRepositoryExists:
    """RiskStateRepository 존재 테스트"""

    def test_repository_class_exists(self):
        """RiskStateRepository 클래스가 존재해야 함"""
        from src.infrastructure.adapters.persistence.risk_state_repository import RiskStateRepository
        assert RiskStateRepository is not None

    def test_repository_has_required_methods(self):
        """RiskStateRepository에 필수 메서드가 있어야 함"""
        from src.infrastructure.adapters.persistence.risk_state_repository import RiskStateRepository

        assert hasattr(RiskStateRepository, 'save')
        assert hasattr(RiskStateRepository, 'load_by_date')
        assert hasattr(RiskStateRepository, 'load_all')
        assert hasattr(RiskStateRepository, 'calculate_weekly_pnl')


class TestRiskStateRepositorySave:
    """RiskStateRepository.save() 테스트"""

    @pytest.mark.asyncio
    async def test_save_creates_new_record(self):
        """새 상태 저장 시 DB에 레코드 생성"""
        from src.infrastructure.adapters.persistence.risk_state_repository import RiskStateRepository
        from backend.app.schemas.risk_state import RiskStateCreate

        # Given
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        # Mock: 기존 레코드 없음 (새 레코드 생성 테스트)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = RiskStateRepository(mock_session)
        state_data = RiskStateCreate(
            state_date=date.today(),
            daily_pnl=Decimal("1.5"),
            daily_trade_count=3,
            weekly_pnl=Decimal("5.0"),
            safe_mode=False,
            safe_mode_reason="",
            last_trade_time=None
        )

        # When
        result = await repo.save(state_data)

        # Then
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_updates_existing_record(self):
        """기존 상태 업데이트 시 레코드 수정"""
        from src.infrastructure.adapters.persistence.risk_state_repository import RiskStateRepository
        from backend.app.schemas.risk_state import RiskStateCreate
        from backend.app.models.risk_state import RiskState

        # Given
        mock_session = AsyncMock()
        existing_record = RiskState(
            id=1,
            state_date=date.today(),
            daily_pnl=Decimal("0.0"),
            daily_trade_count=0
        )

        # Mock: 기존 레코드 조회 결과
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_record
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        repo = RiskStateRepository(mock_session)
        state_data = RiskStateCreate(
            state_date=date.today(),
            daily_pnl=Decimal("2.0"),
            daily_trade_count=5,
            weekly_pnl=Decimal("3.0"),
            safe_mode=False,
            safe_mode_reason="",
            last_trade_time=None
        )

        # When
        result = await repo.save(state_data)

        # Then
        mock_session.commit.assert_awaited()


class TestRiskStateRepositoryLoad:
    """RiskStateRepository.load_by_date() 테스트"""

    @pytest.mark.asyncio
    async def test_load_by_date_returns_state(self):
        """날짜로 상태 조회 시 해당 상태 반환"""
        from src.infrastructure.adapters.persistence.risk_state_repository import RiskStateRepository
        from backend.app.models.risk_state import RiskState

        # Given
        mock_session = AsyncMock()
        expected_record = RiskState(
            id=1,
            state_date=date.today(),
            daily_pnl=Decimal("1.5"),
            daily_trade_count=3
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = expected_record
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = RiskStateRepository(mock_session)

        # When
        result = await repo.load_by_date(date.today())

        # Then
        assert result is not None
        assert result.daily_pnl == Decimal("1.5")

    @pytest.mark.asyncio
    async def test_load_by_date_returns_none_when_not_found(self):
        """해당 날짜 상태가 없으면 None 반환"""
        from src.infrastructure.adapters.persistence.risk_state_repository import RiskStateRepository

        # Given
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = RiskStateRepository(mock_session)

        # When
        result = await repo.load_by_date(date.today())

        # Then
        assert result is None


class TestRiskStateRepositoryLoadAll:
    """RiskStateRepository.load_all() 테스트"""

    @pytest.mark.asyncio
    async def test_load_all_returns_recent_states(self):
        """최근 N일간의 상태 반환"""
        from src.infrastructure.adapters.persistence.risk_state_repository import RiskStateRepository
        from backend.app.models.risk_state import RiskState

        # Given
        mock_session = AsyncMock()
        mock_records = [
            RiskState(id=1, state_date=date.today(), daily_pnl=Decimal("1.0")),
            RiskState(id=2, state_date=date.today() - timedelta(days=1), daily_pnl=Decimal("2.0")),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_records
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = RiskStateRepository(mock_session)

        # When
        result = await repo.load_all(days=7)

        # Then
        assert len(result) == 2


class TestRiskStateRepositoryWeeklyPnl:
    """RiskStateRepository.calculate_weekly_pnl() 테스트"""

    @pytest.mark.asyncio
    async def test_calculate_weekly_pnl_sums_daily_pnl(self):
        """7일간 daily_pnl 합계 계산"""
        from src.infrastructure.adapters.persistence.risk_state_repository import RiskStateRepository
        from backend.app.models.risk_state import RiskState

        # Given
        mock_session = AsyncMock()
        mock_records = [
            RiskState(id=1, state_date=date.today(), daily_pnl=Decimal("1.0")),
            RiskState(id=2, state_date=date.today() - timedelta(days=1), daily_pnl=Decimal("2.0")),
            RiskState(id=3, state_date=date.today() - timedelta(days=2), daily_pnl=Decimal("-0.5")),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_records
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = RiskStateRepository(mock_session)

        # When
        result = await repo.calculate_weekly_pnl()

        # Then
        assert result == Decimal("2.5")  # 1.0 + 2.0 + (-0.5)


class TestRiskStateManagerMigration:
    """기존 RiskStateManager → RiskStateRepository 마이그레이션 테스트"""

    def test_risk_state_manager_uses_repository(self):
        """RiskStateManager가 Repository를 사용하도록 변경되었는지 확인"""
        from src.risk.state_manager import RiskStateManager

        # RiskStateManager에 repository 속성 또는 메서드가 있어야 함
        # 또는 새로운 async 메서드가 있어야 함
        assert hasattr(RiskStateManager, 'save_state_async') or \
               hasattr(RiskStateManager, 'set_repository') or \
               hasattr(RiskStateManager, '_repository')

    def test_json_file_dependency_removed(self):
        """JSON 파일 의존성이 제거되었는지 확인"""
        import src.risk.state_manager as state_manager_module
        import inspect

        source = inspect.getsource(state_manager_module)

        # JSON 파일 관련 코드가 제거되었는지 확인
        # (또는 deprecated 표시가 있는지)
        # 이 테스트는 Phase 2 완료 후 통과해야 함
        assert "risk_state.json" not in source or "DEPRECATED" in source


# 테스트 실행용 fixture
@pytest.fixture(autouse=True)
def reset_imports():
    """각 테스트 후 import 캐시 정리"""
    yield
    # 테스트 후 정리
    import sys
    modules_to_remove = [
        key for key in sys.modules.keys()
        if 'risk_state' in key
    ]
    for module in modules_to_remove:
        sys.modules.pop(module, None)
