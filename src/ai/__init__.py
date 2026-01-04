"""AI 분석 모듈

⚠️ DEPRECATED - Clean Architecture Migration 완료 (2026-01-04)

이 모듈의 모든 기능은 다음으로 마이그레이션되었습니다:
- AIPort (src/application/ports/outbound/ai_port.py)
- OpenAIAdapter (src/infrastructure/adapters/ai/openai_adapter.py)
- ManagePositionUseCase (src/application/use_cases/manage_position.py)
- AnalyzeMarketUseCase (src/application/use_cases/analyze_market.py)

레거시 파일 삭제됨:
- EntryAnalyzer → 제거됨 (백테스팅 기반으로 대체)
- PositionAnalyzer → ManagePositionUseCase + 규칙 기반 로직
- AIService → Container.get_ai_port()
- market_correlation.py → src/domain/services/market_analysis.py
- validator.py → src/infrastructure/adapters/validation.py

이 디렉토리는 향후 제거 예정입니다.
"""

__all__ = []
