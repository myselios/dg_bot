---
description: TDD 규율 복원 및 테스트 커버리지 향상
argument-hint: [대상 모듈/슬라이스]
---

# Test Debt Recovery 실행

다음 영역에 대한 테스트 부채 복구를 시작하세요: $ARGUMENTS

## 복구 워크플로우:
1. **Phase 0**: 베이스라인 측정 및 타겟 선정
2. **Phase 1**: 특성화 테스트 작성 (RED)
3. **Phase 2**: 테스트 통과시키기 (GREEN)
4. **Phase 3**: 테스트 하에서 리팩토링 (REFACTOR)
5. **Phase 4**: 안정성 강화 (선택)

## 우선순위 대상:
- 주문 실행 (ExecuteTradeUseCase)
- 포지션 관리 (stop loss / take profit)
- 스케줄러 경계 (중복 방지, 멱등성)
- AI 결정 경계

## 참조
`.claude/skills/test-debt-recovery/SKILL.md` 워크플로우를 따르세요.
