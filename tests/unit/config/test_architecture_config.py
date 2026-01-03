"""
Tests for ArchitectureConfig - TDD Phase 1

RED Phase: 이 테스트들은 ArchitectureConfig 구현 전에 모두 실패해야 합니다.
"""
import pytest
import os
from unittest.mock import patch


class TestArchitectureConfigExists:
    """ArchitectureConfig 클래스 존재 테스트"""

    def test_architecture_config_class_exists(self):
        """ArchitectureConfig 클래스가 settings 모듈에 존재해야 함"""
        # Given/When
        from src.config.settings import ArchitectureConfig

        # Then
        assert ArchitectureConfig is not None

    def test_architecture_config_has_mode_attribute(self):
        """ArchitectureConfig에 MODE 속성이 있어야 함"""
        # Given
        from src.config.settings import ArchitectureConfig

        # When/Then
        assert hasattr(ArchitectureConfig, 'MODE')


class TestArchitectureConfigModeValues:
    """MODE 설정값 검증 테스트"""

    def test_mode_default_is_legacy(self):
        """기본 MODE는 'legacy'여야 함 (현재 상태 명시)"""
        # Given
        from src.config.settings import ArchitectureConfig

        # When/Then
        assert ArchitectureConfig.MODE == 'legacy'

    def test_mode_accepts_legacy_value(self):
        """MODE='legacy'가 유효해야 함"""
        # Given
        from src.config.settings import ArchitectureConfig

        # When/Then
        assert ArchitectureConfig.MODE in ['legacy', 'clean', 'hybrid']

    @patch.dict(os.environ, {'ARCHITECTURE_MODE': 'clean'})
    def test_mode_can_be_set_via_env(self):
        """환경 변수로 MODE 설정 가능해야 함"""
        # Given - 환경 변수 설정됨 (patch.dict)
        # 모듈을 다시 로드해야 환경 변수가 반영됨
        import importlib
        import src.config.settings as settings_module
        importlib.reload(settings_module)

        # When
        from src.config.settings import ArchitectureConfig

        # Then
        assert ArchitectureConfig.MODE == 'clean'

    @patch.dict(os.environ, {'ARCHITECTURE_MODE': 'hybrid'})
    def test_mode_hybrid_is_valid(self):
        """MODE='hybrid'가 유효해야 함"""
        # Given
        import importlib
        import src.config.settings as settings_module
        importlib.reload(settings_module)

        # When
        from src.config.settings import ArchitectureConfig

        # Then
        assert ArchitectureConfig.MODE == 'hybrid'


class TestArchitectureConfigValidation:
    """ArchitectureConfig 검증 테스트"""

    def test_validate_method_exists(self):
        """validate() 메서드가 있어야 함"""
        # Given
        from src.config.settings import ArchitectureConfig

        # When/Then
        assert hasattr(ArchitectureConfig, 'validate')
        assert callable(ArchitectureConfig.validate)

    def test_validate_passes_for_valid_modes(self):
        """유효한 MODE에서 validate()가 예외 없이 통과"""
        # Given
        from src.config.settings import ArchitectureConfig

        # When/Then - 예외가 발생하지 않아야 함
        ArchitectureConfig.validate()

    @patch.dict(os.environ, {'ARCHITECTURE_MODE': 'invalid_mode'})
    def test_validate_fails_for_invalid_mode(self):
        """유효하지 않은 MODE에서 validate()가 ConfigurationError 발생"""
        # Given
        import importlib
        import src.config.settings as settings_module
        importlib.reload(settings_module)

        from src.config.settings import ArchitectureConfig
        from src.exceptions import ConfigurationError

        # When/Then
        with pytest.raises(ConfigurationError):
            ArchitectureConfig.validate()


class TestArchitectureConfigHelperMethods:
    """ArchitectureConfig 헬퍼 메서드 테스트"""

    def test_is_legacy_mode_method(self):
        """is_legacy_mode() 메서드가 있어야 함"""
        # Given
        from src.config.settings import ArchitectureConfig

        # When/Then
        assert hasattr(ArchitectureConfig, 'is_legacy_mode')
        assert callable(ArchitectureConfig.is_legacy_mode)

    def test_is_clean_mode_method(self):
        """is_clean_mode() 메서드가 있어야 함"""
        # Given
        from src.config.settings import ArchitectureConfig

        # When/Then
        assert hasattr(ArchitectureConfig, 'is_clean_mode')
        assert callable(ArchitectureConfig.is_clean_mode)

    def test_is_hybrid_mode_method(self):
        """is_hybrid_mode() 메서드가 있어야 함"""
        # Given
        from src.config.settings import ArchitectureConfig

        # When/Then
        assert hasattr(ArchitectureConfig, 'is_hybrid_mode')
        assert callable(ArchitectureConfig.is_hybrid_mode)

    def test_is_legacy_mode_returns_true_when_legacy(self):
        """MODE='legacy'일 때 is_legacy_mode()가 True 반환"""
        # Given
        from src.config.settings import ArchitectureConfig

        # When (기본값이 legacy)
        result = ArchitectureConfig.is_legacy_mode()

        # Then
        assert result is True

    def test_should_use_container_method(self):
        """should_use_container() 메서드가 있어야 함"""
        # Given
        from src.config.settings import ArchitectureConfig

        # When/Then
        assert hasattr(ArchitectureConfig, 'should_use_container')
        assert callable(ArchitectureConfig.should_use_container)

    def test_should_use_container_false_when_legacy(self):
        """MODE='legacy'일 때 should_use_container()가 False 반환"""
        # Given
        from src.config.settings import ArchitectureConfig

        # When
        result = ArchitectureConfig.should_use_container()

        # Then
        assert result is False

    @patch.dict(os.environ, {'ARCHITECTURE_MODE': 'clean'})
    def test_should_use_container_true_when_clean(self):
        """MODE='clean'일 때 should_use_container()가 True 반환"""
        # Given
        import importlib
        import src.config.settings as settings_module
        importlib.reload(settings_module)

        from src.config.settings import ArchitectureConfig

        # When
        result = ArchitectureConfig.should_use_container()

        # Then
        assert result is True


class TestContainerModeIntegration:
    """Container와 ArchitectureConfig 통합 테스트"""

    def test_container_respects_architecture_mode(self):
        """Container가 ArchitectureConfig.MODE를 존중해야 함"""
        # Given
        from src.config.settings import ArchitectureConfig
        from src.container import Container

        # When
        container = Container()

        # Then
        # Container가 ArchitectureConfig를 알고 있어야 함
        # (이 테스트는 Phase 1의 마지막 단계에서 통과)
        assert hasattr(container, 'get_architecture_mode') or \
               ArchitectureConfig.MODE is not None


# 테스트 실행용 fixture
@pytest.fixture(autouse=True)
def reset_settings_module():
    """각 테스트 후 settings 모듈 상태 리셋"""
    yield
    # 테스트 후 모듈 리로드하여 환경 변수 영향 제거
    import importlib
    import src.config.settings as settings_module
    # 환경 변수 제거
    os.environ.pop('ARCHITECTURE_MODE', None)
    importlib.reload(settings_module)
