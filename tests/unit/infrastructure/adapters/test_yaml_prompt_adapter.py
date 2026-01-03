"""
YAMLPromptAdapter Tests

TDD - YAML 기반 프롬프트 어댑터
"""
import pytest
from pathlib import Path

from src.infrastructure.adapters.prompt.yaml_prompt_adapter import YAMLPromptAdapter
from src.domain.value_objects.prompt_version import PromptType, PromptVersion


class TestYAMLPromptAdapterCreation:
    """YAMLPromptAdapter 생성 테스트"""

    def test_create_with_default_path(self):
        """Given: 기본 경로 When: 생성 Then: 어댑터 생성"""
        adapter = YAMLPromptAdapter()
        assert adapter is not None

    def test_create_with_custom_path(self, tmp_path):
        """Given: 커스텀 경로 When: 생성 Then: 해당 경로 사용"""
        adapter = YAMLPromptAdapter(prompts_dir=tmp_path)
        assert adapter.prompts_dir == tmp_path


class TestYAMLPromptAdapterGetPrompt:
    """get_prompt 테스트"""

    @pytest.fixture
    def adapter(self):
        return YAMLPromptAdapter()

    @pytest.mark.asyncio
    async def test_get_entry_prompt(self, adapter):
        """Given: ENTRY 타입 When: get_prompt Then: 프롬프트 반환"""
        prompt = await adapter.get_prompt(PromptType.ENTRY)

        assert isinstance(prompt, str)
        assert "Risk Hunter" in prompt

    @pytest.mark.asyncio
    async def test_get_exit_prompt(self, adapter):
        """Given: EXIT 타입 When: get_prompt Then: 프롬프트 반환"""
        prompt = await adapter.get_prompt(PromptType.EXIT)

        assert isinstance(prompt, str)
        assert "Position Manager" in prompt

    @pytest.mark.asyncio
    async def test_get_general_prompt(self, adapter):
        """Given: GENERAL 타입 When: get_prompt Then: 프롬프트 반환"""
        prompt = await adapter.get_prompt(PromptType.GENERAL)

        assert isinstance(prompt, str)
        assert "market analyst" in prompt.lower()


class TestYAMLPromptAdapterGetCurrentVersion:
    """get_current_version 테스트"""

    @pytest.fixture
    def adapter(self):
        return YAMLPromptAdapter()

    @pytest.mark.asyncio
    async def test_get_current_version(self, adapter):
        """Given: 프롬프트 타입 When: get_current_version Then: 버전 반환"""
        version = await adapter.get_current_version(PromptType.ENTRY)

        assert isinstance(version, PromptVersion)
        assert version.prompt_type == PromptType.ENTRY
        assert "v2" in version.version


class TestYAMLPromptAdapterRenderPrompt:
    """render_prompt 테스트"""

    @pytest.fixture
    def adapter(self):
        return YAMLPromptAdapter()

    @pytest.mark.asyncio
    async def test_render_with_context(self, adapter):
        """Given: 컨텍스트 When: render_prompt Then: 변수 대체"""
        context = {
            "ticker": "KRW-BTC",
            "timestamp": "2026-01-03 10:00",
            "regime": "TRENDING_UP",
            "atr_percent": "2.5",
            "breakout_strength": "STRONG",
            "risk_budget": "2.0",
            "rsi": "55",
            "volume_ratio": "1.5",
            "macd_status": "bullish",
            "bb_position": "0.7",
            "btc_dominance": "45.5",
            "fear_greed": "55",
            "flash_crash_risk": "low",
            "backtest_summary": "Strong performance",
        }

        rendered = await adapter.render_prompt(PromptType.ENTRY, context)

        assert "KRW-BTC" in rendered
        assert "TRENDING_UP" in rendered
        assert "2.5" in rendered

    @pytest.mark.asyncio
    async def test_render_with_defaults(self, adapter):
        """Given: 기본 변수 When: render_prompt Then: 기본값 적용"""
        context = {"ticker": "KRW-BTC"}

        # system_prompt에는 기본값이 있는 변수가 있음
        rendered = await adapter.render_prompt(PromptType.ENTRY, context)

        # 기본값이 적용되어야 함
        assert "5.0" in rendered or "0.8" in rendered  # max_atr_percent or min_volume_ratio


class TestYAMLPromptAdapterListVersions:
    """list_versions 테스트"""

    @pytest.fixture
    def adapter(self):
        return YAMLPromptAdapter()

    @pytest.mark.asyncio
    async def test_list_versions(self, adapter):
        """Given: 프롬프트 타입 When: list_versions Then: 버전 목록"""
        versions = await adapter.list_versions(PromptType.ENTRY)

        assert isinstance(versions, list)
        assert len(versions) >= 1
        assert "v2.0.0" in versions


class TestYAMLPromptAdapterValidatePrompt:
    """validate_prompt 테스트"""

    @pytest.fixture
    def adapter(self):
        return YAMLPromptAdapter()

    @pytest.mark.asyncio
    async def test_validate_valid_prompt(self, adapter):
        """Given: 유효한 프롬프트 When: validate_prompt Then: True"""
        prompt = "This is a valid prompt with sufficient content for analysis."
        result = await adapter.validate_prompt(prompt)
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_empty_prompt(self, adapter):
        """Given: 빈 프롬프트 When: validate_prompt Then: False"""
        result = await adapter.validate_prompt("")
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_short_prompt(self, adapter):
        """Given: 짧은 프롬프트 When: validate_prompt Then: False"""
        result = await adapter.validate_prompt("short")
        assert result is False


class TestYAMLPromptAdapterLoadTemplate:
    """_load_template 내부 메서드 테스트"""

    @pytest.fixture
    def adapter(self):
        return YAMLPromptAdapter()

    def test_load_entry_template(self, adapter):
        """Given: entry 템플릿 When: _load_template Then: 로드"""
        template = adapter._load_template(PromptType.ENTRY)

        assert template is not None
        assert "version" in template
        assert "system_prompt" in template
        assert "user_prompt" in template

    def test_load_template_cached(self, adapter):
        """Given: 두 번 로드 When: _load_template Then: 캐시 사용"""
        t1 = adapter._load_template(PromptType.ENTRY)
        t2 = adapter._load_template(PromptType.ENTRY)

        assert t1 is t2  # 같은 객체 (캐시됨)
