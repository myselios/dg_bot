"""
PromptVersion Value Object Tests

TDD - Red: 테스트 먼저 작성
프롬프트 버전 관리를 위한 Value Object
"""
import pytest
from datetime import datetime

from src.domain.value_objects.prompt_version import (
    PromptVersion,
    PromptType,
)


class TestPromptType:
    """프롬프트 유형 열거형 테스트"""

    def test_prompt_type_values(self):
        """Given: 프롬프트 유형 When: 값 확인 Then: 정의된 유형"""
        assert PromptType.ENTRY.value == "entry"
        assert PromptType.EXIT.value == "exit"
        assert PromptType.GENERAL.value == "general"


class TestPromptVersionCreation:
    """PromptVersion 생성 테스트"""

    def test_create_prompt_version(self):
        """Given: 버전 정보 When: 생성 Then: 올바른 값"""
        version = PromptVersion(
            version="v2.0.0",
            prompt_type=PromptType.ENTRY,
            template_hash="abc123def456",
        )

        assert version.version == "v2.0.0"
        assert version.prompt_type == PromptType.ENTRY
        assert version.template_hash == "abc123def456"

    def test_create_with_description(self):
        """Given: 설명 포함 When: 생성 Then: 설명 저장"""
        version = PromptVersion(
            version="v2.0.0",
            prompt_type=PromptType.ENTRY,
            template_hash="abc123",
            description="Risk hunter prompt with dynamic thresholds",
        )

        assert "Risk hunter" in version.description

    def test_immutable(self):
        """Given: 생성된 객체 When: 수정 시도 Then: FrozenInstanceError"""
        version = PromptVersion(
            version="v2.0.0",
            prompt_type=PromptType.ENTRY,
            template_hash="abc123",
        )

        with pytest.raises(Exception):
            version.version = "v3.0.0"


class TestPromptVersionFactoryMethods:
    """PromptVersion 팩토리 메서드 테스트"""

    def test_from_template(self):
        """Given: 템플릿 문자열 When: from_template Then: 해시 자동 생성"""
        template = """
        You are a risk hunter.
        Analyze the following market data and decide:
        - ALLOW: if safe to enter
        - BLOCK: if risks detected
        """

        version = PromptVersion.from_template(
            version="v2.0.0",
            prompt_type=PromptType.ENTRY,
            template=template,
        )

        assert version.version == "v2.0.0"
        assert version.template_hash is not None
        assert len(version.template_hash) == 64  # SHA256

    def test_from_template_hash_consistency(self):
        """Given: 동일한 템플릿 When: from_template 2회 Then: 동일한 해시"""
        template = "Same template content"

        v1 = PromptVersion.from_template("v1", PromptType.ENTRY, template)
        v2 = PromptVersion.from_template("v1", PromptType.ENTRY, template)

        assert v1.template_hash == v2.template_hash

    def test_from_template_different_hash(self):
        """Given: 다른 템플릿 When: from_template Then: 다른 해시"""
        v1 = PromptVersion.from_template("v1", PromptType.ENTRY, "Template A")
        v2 = PromptVersion.from_template("v1", PromptType.ENTRY, "Template B")

        assert v1.template_hash != v2.template_hash

    def test_entry_v1(self):
        """Given: entry_v1 팩토리 When: 호출 Then: 진입 프롬프트 v1"""
        version = PromptVersion.entry_v1()

        assert version.prompt_type == PromptType.ENTRY
        assert version.version == "v1.0.0"

    def test_current(self):
        """Given: current 팩토리 When: 호출 Then: 최신 버전"""
        version = PromptVersion.current(PromptType.ENTRY)

        assert version.prompt_type == PromptType.ENTRY
        assert "v" in version.version


class TestPromptVersionMethods:
    """PromptVersion 메서드 테스트"""

    def test_is_compatible_with(self):
        """Given: 버전들 When: is_compatible_with Then: 호환성 확인"""
        v1 = PromptVersion(
            version="v2.0.0",
            prompt_type=PromptType.ENTRY,
            template_hash="abc123",
        )
        v2 = PromptVersion(
            version="v2.1.0",
            prompt_type=PromptType.ENTRY,
            template_hash="def456",
        )
        v3 = PromptVersion(
            version="v3.0.0",
            prompt_type=PromptType.ENTRY,
            template_hash="ghi789",
        )

        # 같은 major 버전 = 호환
        assert v1.is_compatible_with(v2) is True
        # 다른 major 버전 = 비호환
        assert v1.is_compatible_with(v3) is False

    def test_major_version(self):
        """Given: 버전 When: major_version Then: major 숫자"""
        v = PromptVersion("v2.1.0", PromptType.ENTRY, "abc")
        assert v.major_version == 2

        v2 = PromptVersion("v10.2.3", PromptType.EXIT, "def")
        assert v2.major_version == 10

    def test_minor_version(self):
        """Given: 버전 When: minor_version Then: minor 숫자"""
        v = PromptVersion("v2.1.0", PromptType.ENTRY, "abc")
        assert v.minor_version == 1

    def test_to_dict(self):
        """Given: PromptVersion When: to_dict Then: 딕셔너리 변환"""
        version = PromptVersion(
            version="v2.0.0",
            prompt_type=PromptType.ENTRY,
            template_hash="abc123",
            description="Test prompt",
        )

        d = version.to_dict()

        assert d["version"] == "v2.0.0"
        assert d["prompt_type"] == "entry"
        assert d["template_hash"] == "abc123"
        assert d["description"] == "Test prompt"

    def test_to_tracking_id(self):
        """Given: PromptVersion When: to_tracking_id Then: 추적용 ID"""
        version = PromptVersion(
            version="v2.0.0",
            prompt_type=PromptType.ENTRY,
            template_hash="abc123def456",
        )

        tracking_id = version.to_tracking_id()

        # 형식: {type}_{version}_{hash_prefix}
        assert tracking_id == "entry_v2.0.0_abc123de"


class TestPromptVersionEquality:
    """동등성 테스트"""

    def test_equal_by_hash(self):
        """Given: 동일한 해시 When: 비교 Then: 동등"""
        v1 = PromptVersion("v2.0.0", PromptType.ENTRY, "abc123")
        v2 = PromptVersion("v2.0.0", PromptType.ENTRY, "abc123")

        assert v1 == v2

    def test_unequal_by_hash(self):
        """Given: 다른 해시 When: 비교 Then: 비동등"""
        v1 = PromptVersion("v2.0.0", PromptType.ENTRY, "abc123")
        v2 = PromptVersion("v2.0.0", PromptType.ENTRY, "def456")

        assert v1 != v2

    def test_unequal_by_type(self):
        """Given: 다른 유형 When: 비교 Then: 비동등"""
        v1 = PromptVersion("v2.0.0", PromptType.ENTRY, "abc123")
        v2 = PromptVersion("v2.0.0", PromptType.EXIT, "abc123")

        assert v1 != v2


class TestPromptVersionStringRepresentation:
    """문자열 표현 테스트"""

    def test_str(self):
        """Given: PromptVersion When: str Then: 간단한 표현"""
        version = PromptVersion("v2.0.0", PromptType.ENTRY, "abc123")
        s = str(version)

        assert "v2.0.0" in s
        assert "entry" in s

    def test_repr(self):
        """Given: PromptVersion When: repr Then: 상세 표현"""
        version = PromptVersion("v2.0.0", PromptType.ENTRY, "abc123")
        r = repr(version)

        assert "PromptVersion" in r
        assert "abc123" in r
