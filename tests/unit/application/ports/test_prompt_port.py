"""
PromptPort Interface Tests

TDD - Port 인터페이스 정의
"""
import pytest
from abc import ABC
from typing import Optional

from src.application.ports.outbound.prompt_port import PromptPort
from src.domain.value_objects.prompt_version import PromptType, PromptVersion
from src.domain.value_objects.market_summary import MarketSummary, MarketRegime, BreakoutStrength
from decimal import Decimal


class MockPromptAdapter(PromptPort):
    """테스트용 Mock 어댑터"""

    async def get_prompt(
        self,
        prompt_type: PromptType,
        version: Optional[str] = None,
    ) -> str:
        return f"Mock prompt for {prompt_type.value}"

    async def get_current_version(self, prompt_type: PromptType) -> PromptVersion:
        return PromptVersion.current(prompt_type)

    async def render_prompt(
        self,
        prompt_type: PromptType,
        context: dict,
        version: Optional[str] = None,
    ) -> str:
        return f"Rendered prompt with {len(context)} context items"

    async def list_versions(self, prompt_type: PromptType) -> list:
        return ["v1.0.0", "v2.0.0"]

    async def validate_prompt(self, prompt: str) -> bool:
        return len(prompt) > 10


class TestPromptPortInterface:
    """PromptPort 인터페이스 테스트"""

    def test_is_abstract(self):
        """Given: PromptPort When: 인스턴스화 시도 Then: TypeError"""
        with pytest.raises(TypeError):
            PromptPort()

    def test_inherits_abc(self):
        """Given: PromptPort When: 부모 클래스 확인 Then: ABC"""
        assert issubclass(PromptPort, ABC)


class TestPromptPortMethods:
    """PromptPort 메서드 테스트 (Mock 사용)"""

    @pytest.fixture
    def adapter(self):
        return MockPromptAdapter()

    @pytest.mark.asyncio
    async def test_get_prompt(self, adapter):
        """Given: 프롬프트 유형 When: get_prompt Then: 프롬프트 반환"""
        prompt = await adapter.get_prompt(PromptType.ENTRY)

        assert isinstance(prompt, str)
        assert "entry" in prompt.lower()

    @pytest.mark.asyncio
    async def test_get_current_version(self, adapter):
        """Given: 프롬프트 유형 When: get_current_version Then: 버전 반환"""
        version = await adapter.get_current_version(PromptType.ENTRY)

        assert isinstance(version, PromptVersion)
        assert version.prompt_type == PromptType.ENTRY

    @pytest.mark.asyncio
    async def test_render_prompt(self, adapter):
        """Given: 컨텍스트 When: render_prompt Then: 렌더링된 프롬프트"""
        context = {
            "ticker": "KRW-BTC",
            "regime": "trending_up",
            "rsi": 55,
        }

        rendered = await adapter.render_prompt(PromptType.ENTRY, context)

        assert isinstance(rendered, str)
        assert "3" in rendered  # 3 context items

    @pytest.mark.asyncio
    async def test_list_versions(self, adapter):
        """Given: 프롬프트 유형 When: list_versions Then: 버전 목록"""
        versions = await adapter.list_versions(PromptType.ENTRY)

        assert isinstance(versions, list)
        assert len(versions) >= 1

    @pytest.mark.asyncio
    async def test_validate_prompt(self, adapter):
        """Given: 프롬프트 When: validate_prompt Then: 유효성 결과"""
        valid = await adapter.validate_prompt("This is a valid prompt text")
        invalid = await adapter.validate_prompt("short")

        assert valid is True
        assert invalid is False
