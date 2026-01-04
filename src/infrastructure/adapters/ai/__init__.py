"""AI adapters.

⚠️ EnhancedOpenAIAdapter 제거됨 (Clean Architecture 마이그레이션 완료)

현재 사용 가능한 AI 어댑터:
- OpenAIAdapter: AIPort 구현체 (Clean Architecture)
"""
from src.infrastructure.adapters.ai.openai_adapter import OpenAIAdapter

__all__ = [
    "OpenAIAdapter",
]
