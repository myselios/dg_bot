---
description: 트레이딩 봇 코드 리뷰 (보안, 성능, 로직)
argument-hint: [파일 또는 모듈 경로]
---

# Trading Review 실행

다음 코드를 리뷰하세요: $ARGUMENTS

## 리뷰 체크리스트:

### 보안
- API 키 하드코딩 여부
- 로그에 민감 데이터 노출 여부
- API 호출 에러 핸들링

### 트레이딩 로직
- 수수료 계산 정확성
- 슬리피지 처리
- 주문 실행 엣지 케이스
- 포지션 관리 안전성

### AI 통합
- 프롬프트 인젝션 방지
- 응답 검증
- 토큰 사용 최적화
- 폴백 처리

### 성능
- DB 쿼리 효율성
- API rate limit 처리
- 백테스팅 메모리 사용

## 참조
`.claude/skills/trading-review/SKILL.md` 체크리스트를 따르세요.
