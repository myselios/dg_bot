"""
YAMLPromptAdapter - YAML 기반 프롬프트 관리 어댑터.

YAML 템플릿에서 프롬프트를 로드하고 렌더링.
프롬프트 버전 관리 및 추적성 확보.
"""
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from src.application.ports.outbound.prompt_port import PromptPort
from src.domain.value_objects.prompt_version import PromptType, PromptVersion


class YAMLPromptAdapter(PromptPort):
    """
    YAML 파일 기반 프롬프트 관리 어댑터.

    src/infrastructure/prompts/ 디렉토리의 YAML 템플릿 사용.
    """

    def __init__(self, prompts_dir: Optional[Path] = None):
        """
        초기화.

        Args:
            prompts_dir: 프롬프트 디렉토리 경로 (기본: src/infrastructure/prompts/)
        """
        if prompts_dir is None:
            # 기본 경로: src/infrastructure/prompts/
            self.prompts_dir = Path(__file__).parent.parent.parent / "prompts"
        else:
            self.prompts_dir = prompts_dir

        # 템플릿 캐시
        self._cache: Dict[PromptType, Dict[str, Any]] = {}

    def _load_template(self, prompt_type: PromptType) -> Dict[str, Any]:
        """
        YAML 템플릿 로드 (캐시 사용).

        Args:
            prompt_type: 프롬프트 유형

        Returns:
            템플릿 딕셔너리
        """
        if prompt_type in self._cache:
            return self._cache[prompt_type]

        file_path = self.prompts_dir / f"{prompt_type.value}.yaml"

        if not file_path.exists():
            raise FileNotFoundError(f"Prompt template not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            template = yaml.safe_load(f)

        self._cache[prompt_type] = template
        return template

    def _render_template(
        self,
        template_str: str,
        context: Dict[str, Any],
        defaults: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        템플릿 문자열에 컨텍스트 적용.

        Args:
            template_str: 템플릿 문자열
            context: 컨텍스트 값들
            defaults: 기본값들

        Returns:
            렌더링된 문자열
        """
        result = template_str

        # 기본값 적용
        if defaults:
            for key, value in defaults.items():
                if isinstance(value, dict) and "default" in value:
                    default_val = value["default"]
                    result = result.replace(f"{{{key}}}", str(default_val))

        # 컨텍스트 값 적용
        for key, value in context.items():
            result = result.replace(f"{{{key}}}", str(value))

        return result

    async def get_prompt(
        self,
        prompt_type: PromptType,
        version: Optional[str] = None,
    ) -> str:
        """
        프롬프트 템플릿 반환 (system_prompt).

        Args:
            prompt_type: 프롬프트 유형
            version: 버전 (현재 미사용, 확장용)

        Returns:
            system_prompt 문자열
        """
        template = self._load_template(prompt_type)
        system_prompt = template.get("system_prompt", "")
        variables = template.get("variables", {})

        # 기본값 적용
        return self._render_template(system_prompt, {}, variables)

    async def get_current_version(self, prompt_type: PromptType) -> PromptVersion:
        """
        현재 버전 정보 반환.

        Args:
            prompt_type: 프롬프트 유형

        Returns:
            PromptVersion 객체
        """
        template = self._load_template(prompt_type)
        version_str = template.get("version", "v1.0.0")
        description = template.get("description", "")

        # 템플릿 해시 계산
        system_prompt = template.get("system_prompt", "")
        user_prompt = template.get("user_prompt", "")
        combined = system_prompt + user_prompt
        template_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()

        return PromptVersion(
            version=version_str,
            prompt_type=prompt_type,
            template_hash=template_hash,
            description=description,
        )

    async def render_prompt(
        self,
        prompt_type: PromptType,
        context: Dict[str, Any],
        version: Optional[str] = None,
    ) -> str:
        """
        프롬프트 렌더링 (system_prompt + user_prompt).

        Args:
            prompt_type: 프롬프트 유형
            context: 컨텍스트 데이터
            version: 버전 (현재 미사용)

        Returns:
            렌더링된 전체 프롬프트
        """
        template = self._load_template(prompt_type)
        variables = template.get("variables", {})

        system_prompt = template.get("system_prompt", "")
        user_prompt = template.get("user_prompt", "")

        # 기본값 + 컨텍스트 적용
        rendered_system = self._render_template(system_prompt, context, variables)
        rendered_user = self._render_template(user_prompt, context, variables)

        return f"{rendered_system}\n\n---\n\n{rendered_user}"

    async def list_versions(self, prompt_type: PromptType) -> List[str]:
        """
        사용 가능한 버전 목록.

        현재는 단일 버전만 지원. 향후 버전별 파일로 확장 가능.

        Args:
            prompt_type: 프롬프트 유형

        Returns:
            버전 문자열 목록
        """
        template = self._load_template(prompt_type)
        version_str = template.get("version", "v1.0.0")
        return [version_str]

    async def validate_prompt(self, prompt: str) -> bool:
        """
        프롬프트 유효성 검사.

        Args:
            prompt: 검사할 프롬프트

        Returns:
            유효 여부
        """
        # 기본 검증: 빈 문자열 또는 너무 짧은 문자열
        if not prompt or len(prompt.strip()) < 10:
            return False

        return True
