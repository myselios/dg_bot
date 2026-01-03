"""
Tests for Scheduler Layer Isolation - TDD Phase 4

RED Phase: 이 테스트들은 Scheduler가 main.py 의존성을 제거하기 전에 실패합니다.

목표:
- scheduler.py → main.py 순환 의존성 제거
- Scheduler가 TradingOrchestrator만 사용하도록 변경
- 계층 의존성 검증 (Infrastructure → Application)
"""
import pytest
import ast
import re
from pathlib import Path


class TestSchedulerNoMainImport:
    """scheduler.py가 main.py를 import하지 않는지 테스트"""

    def test_no_from_main_import(self):
        """scheduler.py에서 'from main import' 패턴 없어야 함"""
        scheduler_path = Path("backend/app/core/scheduler.py")
        content = scheduler_path.read_text()

        matches = re.findall(r'from main import', content)
        assert len(matches) == 0, \
            f"scheduler.py에서 'from main import' 발견: {matches}"

    def test_no_import_main(self):
        """scheduler.py에서 'import main' 패턴 없어야 함"""
        scheduler_path = Path("backend/app/core/scheduler.py")
        content = scheduler_path.read_text()

        # 'import main'이지만 'from X import main_*'은 제외
        lines = content.split('\n')
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('import main') and not stripped.startswith('import main_'):
                assert False, f"scheduler.py 라인 {i+1}에서 'import main' 발견: {line}"


class TestSchedulerUsesTradingOrchestrator:
    """scheduler.py가 TradingOrchestrator를 사용하는지 테스트"""

    def test_imports_trading_orchestrator(self):
        """scheduler.py가 TradingOrchestrator를 import해야 함"""
        scheduler_path = Path("backend/app/core/scheduler.py")
        content = scheduler_path.read_text()

        # TradingOrchestrator import 확인
        has_orchestrator_import = (
            'from src.application.services.trading_orchestrator import TradingOrchestrator' in content or
            'from src.application.services import TradingOrchestrator' in content or
            'TradingOrchestrator' in content
        )

        assert has_orchestrator_import, \
            "scheduler.py에서 TradingOrchestrator import가 없습니다"

    def test_trading_job_uses_orchestrator(self):
        """trading_job()이 TradingOrchestrator를 사용해야 함"""
        scheduler_path = Path("backend/app/core/scheduler.py")
        content = scheduler_path.read_text()

        # trading_job 함수 내에서 orchestrator 사용 확인
        # 'orchestrator.execute_trading_cycle' 또는 'get_trading_orchestrator'
        has_orchestrator_usage = (
            'orchestrator.execute_trading_cycle' in content or
            'get_trading_orchestrator()' in content or
            '.execute_trading_cycle(' in content
        )

        assert has_orchestrator_usage, \
            "trading_job()에서 TradingOrchestrator 사용이 없습니다"

    def test_position_management_uses_orchestrator(self):
        """position_management_job()이 TradingOrchestrator를 사용해야 함"""
        scheduler_path = Path("backend/app/core/scheduler.py")
        content = scheduler_path.read_text()

        # position_management_job 함수 내에서 orchestrator 사용 확인
        has_orchestrator_usage = (
            'orchestrator.execute_position_management' in content or
            '.execute_position_management(' in content
        )

        assert has_orchestrator_usage, \
            "position_management_job()에서 TradingOrchestrator 사용이 없습니다"


class TestSchedulerNoGetLegacyServices:
    """scheduler.py에서 get_legacy_services 제거 테스트"""

    def test_no_get_legacy_services_function(self):
        """get_legacy_services() 함수가 제거되어야 함"""
        scheduler_path = Path("backend/app/core/scheduler.py")
        content = scheduler_path.read_text()

        # get_legacy_services 함수 정의 제거 확인
        has_legacy_services = 'def get_legacy_services(' in content

        assert not has_legacy_services, \
            "scheduler.py에 get_legacy_services() 함수가 남아있습니다"

    def test_no_getattr_client_pattern(self):
        """scheduler.py에서 getattr(*, '_client') 패턴 제거"""
        scheduler_path = Path("backend/app/core/scheduler.py")
        content = scheduler_path.read_text()

        matches = re.findall(r"getattr\([^)]*'_client'", content)

        assert len(matches) == 0, \
            f"scheduler.py에서 getattr.*_client 패턴 발견: {matches}"


class TestContainerHasOrchestratorMethod:
    """Container가 TradingOrchestrator를 제공하는지 테스트"""

    def test_container_has_get_trading_orchestrator(self):
        """Container에 get_trading_orchestrator() 메서드가 있어야 함"""
        from src.container import Container

        assert hasattr(Container, 'get_trading_orchestrator'), \
            "Container에 get_trading_orchestrator() 메서드가 없습니다"

    def test_get_trading_orchestrator_returns_instance(self):
        """get_trading_orchestrator()가 TradingOrchestrator 인스턴스를 반환"""
        from src.container import Container
        from src.application.services.trading_orchestrator import TradingOrchestrator

        container = Container()
        orchestrator = container.get_trading_orchestrator()

        assert isinstance(orchestrator, TradingOrchestrator), \
            f"get_trading_orchestrator()가 TradingOrchestrator가 아닌 {type(orchestrator)}를 반환"


class TestLayerDependencies:
    """계층 의존성 검증 테스트"""

    def test_scheduler_only_imports_application_layer(self):
        """
        scheduler.py는 application layer만 import해야 함
        (presentation layer인 main.py 금지)
        """
        scheduler_path = Path("backend/app/core/scheduler.py")
        content = scheduler_path.read_text()

        # 허용되는 import 패턴
        allowed_patterns = [
            'from src.application',
            'from src.container',
            'from src.config',
            'from src.utils',
            'from backend.app',
            'from src.trading',  # 파이프라인 관련
            'from src.risk',  # 리스크 관리
        ]

        # 금지되는 import 패턴 (presentation layer)
        forbidden_patterns = [
            'from main import',
            'import main',
        ]

        for forbidden in forbidden_patterns:
            assert forbidden not in content, \
                f"scheduler.py에서 금지된 import 발견: {forbidden}"


# 테스트 실행용 fixture
@pytest.fixture(autouse=True)
def reset_imports():
    """각 테스트 후 import 캐시 정리"""
    yield
    import sys
    modules_to_remove = [
        key for key in sys.modules.keys()
        if 'scheduler' in key or 'orchestrator' in key.lower()
    ]
    for module in modules_to_remove:
        sys.modules.pop(module, None)
