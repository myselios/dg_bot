"""
PromptVersion Value Object

프롬프트 버전 관리를 위한 Value Object.
프롬프트 변경 추적 및 AI 판단 재현성 확보.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class PromptType(Enum):
    """프롬프트 유형"""

    ENTRY = "entry"  # 진입 판단
    EXIT = "exit"  # 종료 판단
    GENERAL = "general"  # 일반 분석


# 현재 버전 상수
CURRENT_VERSIONS = {
    PromptType.ENTRY: "v2.0.0",
    PromptType.EXIT: "v2.0.0",
    PromptType.GENERAL: "v2.0.0",
}


@dataclass(frozen=True)
class PromptVersion:
    """
    프롬프트 버전 Value Object.

    프롬프트 템플릿의 버전과 해시를 관리하여
    AI 판단의 재현성과 추적성을 확보.

    Attributes:
        version: 시맨틱 버전 (예: "v2.0.0")
        prompt_type: 프롬프트 유형 (entry/exit/general)
        template_hash: 템플릿 내용의 SHA256 해시
        description: 프롬프트 설명 (선택)
    """

    version: str
    prompt_type: PromptType
    template_hash: str
    description: Optional[str] = None

    # --- Factory Methods ---

    @classmethod
    def from_template(
        cls,
        version: str,
        prompt_type: PromptType,
        template: str,
        description: Optional[str] = None,
    ) -> PromptVersion:
        """
        템플릿 문자열로부터 버전 생성.

        템플릿 내용의 SHA256 해시를 자동 계산.
        """
        template_hash = hashlib.sha256(template.encode("utf-8")).hexdigest()
        return cls(
            version=version,
            prompt_type=prompt_type,
            template_hash=template_hash,
            description=description,
        )

    @classmethod
    def entry_v1(cls) -> PromptVersion:
        """진입 프롬프트 v1.0.0"""
        return cls(
            version="v1.0.0",
            prompt_type=PromptType.ENTRY,
            template_hash="legacy_entry_v1",
            description="Legacy entry prompt v1",
        )

    @classmethod
    def current(cls, prompt_type: PromptType) -> PromptVersion:
        """현재 최신 버전 반환"""
        version = CURRENT_VERSIONS.get(prompt_type, "v1.0.0")
        return cls(
            version=version,
            prompt_type=prompt_type,
            template_hash=f"current_{prompt_type.value}",
            description=f"Current {prompt_type.value} prompt",
        )

    # --- Query Methods ---

    @property
    def major_version(self) -> int:
        """Major 버전 숫자 추출"""
        match = re.match(r"v?(\d+)", self.version)
        return int(match.group(1)) if match else 0

    @property
    def minor_version(self) -> int:
        """Minor 버전 숫자 추출"""
        match = re.match(r"v?(\d+)\.(\d+)", self.version)
        return int(match.group(2)) if match else 0

    def is_compatible_with(self, other: PromptVersion) -> bool:
        """
        다른 버전과 호환되는지 확인.

        같은 major 버전이면 호환으로 간주.
        """
        return self.major_version == other.major_version

    def to_tracking_id(self) -> str:
        """
        추적용 고유 ID 생성.

        형식: {type}_{version}_{hash_prefix}
        """
        hash_prefix = self.template_hash[:8]
        return f"{self.prompt_type.value}_{self.version}_{hash_prefix}"

    # --- Conversion Methods ---

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "version": self.version,
            "prompt_type": self.prompt_type.value,
            "template_hash": self.template_hash,
            "description": self.description,
            "tracking_id": self.to_tracking_id(),
        }

    def __str__(self) -> str:
        """문자열 표현"""
        return f"PromptVersion({self.prompt_type.value} {self.version})"

    def __repr__(self) -> str:
        """상세 표현"""
        return (
            f"PromptVersion(version={self.version!r}, "
            f"prompt_type={self.prompt_type}, "
            f"template_hash={self.template_hash!r})"
        )
