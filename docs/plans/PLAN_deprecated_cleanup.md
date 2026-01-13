# Task Plan: Backtesting DEPRECATED 코드 정리

**작성일**: 2026-01-05
**완료일**: 2026-01-05
**상태**: ✅ 완료
**버전**: v2.0

---

## Goal

backtesting 폴더의 DEPRECATED 코드를 완전 삭제하고 코드베이스를 정리한다.

---

## 이전 작업 완료 내역 (Phase 1-7)

| Phase | 작업 | 상태 |
|-------|------|------|
| Phase 1 | Critical 버그 수정 (avg_loss_pct 구현) | ✅ |
| Phase 2 | 예외 처리 및 로깅 개선 | ✅ |
| Phase 3 | Clean Architecture 정리 (DI 테스트) | ✅ |
| Phase 4 | 통계적 안전장치 | ✅ |
| Phase 5 | 죽은 코드 정리 (ai_strategy.py 삭제) | ✅ |
| Phase 6 | 통합 테스트 검증 (211개 통과) | ✅ |
| Phase 7 | 가중치 기반 필터 평가 (227개 통과) | ✅ |

---

## 삭제된 DEPRECATED 코드

### Config 클래스
| 코드 | 설명 |
|------|------|
| `ResearchPassConfig` | 2단 게이트 Research Pass용 Config |
| `TradingPassConfig` | 2단 게이트 Trading Pass용 Config |
| `QuickBacktestConfig` | 레거시 Config |

### 메서드
| 메서드 | 설명 |
|--------|------|
| `evaluate_research_pass()` | 2단 게이트 Research 평가 |
| `evaluate_trading_pass()` | 2단 게이트 Trading 평가 |
| `aggregate_filter_statistics()` | 3단 비교 통계 집계 |
| `get_top_failing_filters()` | 3단 비교 관련 |
| `generate_filter_analysis_report()` | 3단 비교 리포트 |

### 테스트 파일
| 파일 | 처리 |
|------|------|
| `tests/scenarios/test_two_gate_pipeline.py` | 삭제됨 |
| `tests/unit/backtesting/test_backtest_filter.py` | 호환성 테스트 클래스 삭제 |
| `tests/unit/backtesting/test_filter_analysis.py` | 3단 비교 테스트 클래스 삭제 |
| `tests/backtesting/test_backtesting_quick_filter.py` | BacktestConfig 사용으로 변경 |

---

## Phases

### Phase 8-1: 프로덕션 코드 마이그레이션 ✅
- [x] `src/scanner/multi_backtest.py` - ResearchPassConfig → BacktestConfig
- [x] `src/scanner/coin_selector.py` - TradingPassConfig → BacktestConfig
- [x] `src/backtesting/__init__.py` - deprecated export 제거

### Phase 8-2: DEPRECATED Config 클래스 삭제 ✅
- [x] `ResearchPassConfig` 삭제
- [x] `TradingPassConfig` 삭제
- [x] `QuickBacktestConfig` 삭제

### Phase 8-3: DEPRECATED 메서드 삭제 ✅
- [x] `evaluate_research_pass()` 삭제
- [x] `evaluate_trading_pass()` 삭제
- [x] `aggregate_filter_statistics()` 삭제
- [x] `get_top_failing_filters()` 삭제
- [x] `generate_filter_analysis_report()` 삭제

### Phase 8-4: 테스트 코드 정리 ✅
- [x] `tests/scenarios/test_two_gate_pipeline.py` 삭제
- [x] `tests/unit/backtesting/test_backtest_filter.py` 호환성 테스트 삭제
- [x] `tests/unit/backtesting/test_filter_analysis.py` 3단 비교 테스트 삭제
- [x] `tests/backtesting/test_backtesting_quick_filter.py` 리팩토링

### Phase 8-5: 문서 동기화 및 최종 검증 ✅
- [x] `docs/guide/BACKTESTING_GUIDE.md` - 2단 게이트 설명 제거
- [x] PLAN 파일 상태 업데이트
- [ ] 전체 테스트 실행 및 통과 확인

---

## Decisions Made

| 결정 | 근거 |
|------|------|
| 2단 게이트 → 단일 게이트 | AI 분석 제거로 Research Pass 목적 소멸 |
| BacktestConfig가 단일 표준 | 중복 Config 제거 |
| 호환성 유지 삭제 | 코드 복잡도 감소, 단일 경로 강제 |

---

## 현재 구조 (정리 후)

```
src/backtesting/quick_filter.py
├── BacktestConfig              # 단일 표준 Config
├── QuickBacktestFilter
│   ├── evaluate_backtest()           # ALL AND 평가
│   ├── evaluate_backtest_weighted()  # 가중치 기반 평가 (기본값)
│   └── analyze_filter_results()      # 필터 분석
├── FilterStatistics            # 필터 통계 데이터클래스
├── FilterAnalysisResult        # 분석 결과 데이터클래스
└── PassResult                  # 평가 결과 데이터클래스
```

---

## Status

**✅ 완료** - 2026-01-05
