# AI Legacy Code Elimination & Clean Architecture Completion Plan

**Created**: 2026-01-04
**Status**: ⏳ Pending Approval
**Estimated Duration**: 15-20 hours
**Last Updated**: 2026-01-04

---

**⚠️ CRITICAL INSTRUCTIONS**: After completing each phase:
1. ✅ Check off completed task checkboxes
2. 🧪 Run all quality gate validation commands
3. ⚠️ Verify ALL quality gate items pass
4. 📅 Update "Last Updated" date
5. 📝 Document learnings in Notes section
6. ➡️ Only then proceed to next phase

⛔ **DO NOT skip quality gates or proceed with failing checks**

---

## 📋 Overview

### Problem Statement

After multiple attempts to fix the trading pipeline, **basic logic still doesn't work properly** due to:

1. **Architecture Confusion**: Mixed usage of legacy AI code (`src/ai/`) and Clean Architecture (`AIPort`, `UseCases`)
2. **Recurring Parameter Errors**: MAX_TOKENS, max_completion_tokens, DataFrame vs Dict, DTO conversion failures
3. **No Safety Nets**: Missing contract tests to catch parameter mismatches
4. **Documentation Drift**: ARCHITECTURE.md doesn't match actual code behavior
5. **Type System Weakness**: Python's dynamic typing allows mismatches to slip through

### Root Cause Analysis (Why Things Keep Breaking)

#### 🔴 **ROOT CAUSE #1: Architecture Confusion**

**Evidence**:
- `src/trading/pipeline/analysis_stage.py` uses **AIPort** (Clean Architecture)
- `src/trading/pipeline/hybrid_stage.py` uses **PositionAnalyzer** (Legacy)
- `src/scanner/coin_selector.py` uses **EntryAnalyzer** (Legacy)
- `src/container.py` line 305-322: `get_analyze_breakout_use_case()` creates **EnhancedOpenAIAdapter** directly

**Impact**:
- Developers don't know which pattern to follow
- Changes in one place don't propagate correctly
- Testing becomes inconsistent (which mock to use?)

**Why This Causes Parameter Errors**:
- Legacy code has different interfaces than Clean Architecture
- No single contract to validate against
- Changes to OpenAI API affect multiple incompatible implementations

---

#### 🔴 **ROOT CAUSE #2: No Contract Tests**

**Evidence**:
- No tests validating DTO interfaces (`AnalysisRequest`, `TradingDecision`, `TechnicalIndicators`)
- No tests ensuring DataFrame/Dict compatibility
- No tests catching OpenAI API parameter changes

**Impact**:
- Parameter mismatches discovered at runtime, not in tests
- DTO fields can be added/removed without breaking tests
- API changes (max_tokens → max_completion_tokens) break production

**Why This Causes Repeated Failures**:
```python
# Example: This error was NOT caught by tests
indicators = context.technical_indicators  # Dict from legacy code
ai_port.analyze(indicators=indicators)      # Expects TechnicalIndicators DTO
# → AttributeError: 'dict' object has no attribute 'rsi'
```

---

#### 🔴 **ROOT CAUSE #3: Weak Type Boundaries**

**Evidence**:
- `AnalyzeMarketUseCase.analyze()` accepts both `Dict` and `TechnicalIndicators`
- No runtime validation at UseCase entry points
- Python's duck typing hides incompatibilities until runtime

**Impact**:
- Callers pass wrong types without compile-time errors
- DataFrame/Dict confusion not caught until production
- Defensive programming needed everywhere

**Why This Causes Parameter Errors**:
```python
# Example: This ambiguity was NOT caught
chart_data = chart_data.get('day') or chart_data.get('minute60') or chart_data
# → ValueError: The truth value of a DataFrame is ambiguous
```

---

#### 🔴 **ROOT CAUSE #4: Documentation Drift**

**Evidence**:
- `ARCHITECTURE.md` line 139-145 shows `src/ai/` as current structure
- No mention that `AIPort` is now the standard
- Migration guides incomplete or outdated

**Impact**:
- New code follows outdated patterns from docs
- Refactoring becomes confused about target state
- Code reviews miss architectural violations

---

### Success Criteria

✅ **All legacy AI code deleted** (`src/ai/`, `enhanced_openai_adapter.py`)
✅ **100% Clean Architecture** (all AI calls via `AIPort` → `OpenAIAdapter`)
✅ **Contract tests prevent parameter errors** (DTO validation, API compatibility)
✅ **Documentation matches reality** (`ARCHITECTURE.md` shows current state)
✅ **Trading pipeline works end-to-end** (no more parameter errors)

---

## 🎯 Objectives

1. **Prevent Future Parameter Errors** via contract tests and type validation
2. **Complete Clean Architecture Migration** by eliminating all legacy AI code
3. **Update Documentation** to match actual implementation
4. **Strengthen Test Coverage** to catch API changes before production

---

## 🏗 Architecture Decisions

### Decision 1: Use AIPort as Single AI Interface

**Rationale**:
- Single contract eliminates confusion
- Easier to test (one mock interface)
- Changes propagate consistently
- Follows Dependency Inversion Principle

**Implementation**:
- All AI calls go through `Container.get_ai_port()` → `OpenAIAdapter`
- Delete all direct `EntryAnalyzer`, `PositionAnalyzer`, `EnhancedOpenAIAdapter` usage

---

### Decision 2: Extract Legacy Domain Logic to Domain Services

**Rationale**:
- `market_correlation.py` contains pure business logic (CAPM, beta/alpha)
- `validator.py` contains trading rules (RSI, Fakeout, ADX checks)
- These belong in Domain Layer, not mixed with AI adapters

**Implementation**:
- Create `src/domain/services/market_analysis.py` for market correlation
- Create `ValidationPort` + `ValidationAdapter` for trading rules
- Keep logic, delete AI coupling

---

### Decision 3: Contract Tests as First-Class Citizens

**Rationale**:
- Parameter errors are unacceptable in live trading
- Contract tests catch interface violations before runtime
- Prevents regression of DTO mismatches

**Implementation**:
- `tests/contracts/test_ai_port_contract.py` - Validates AIPort interface
- `tests/contracts/test_dto_schemas.py` - Validates DTO serialization
- `tests/contracts/test_openai_api_compatibility.py` - Catches API changes

---

## 📊 Phase Breakdown

### Phase 1: Contract Tests & Type Safety (🔴 HIGHEST PRIORITY)

**Goal**: Prevent future parameter errors by adding safety nets

**Duration**: 3-4 hours

**Test Strategy**:
- **Test Type**: Contract Tests (prevent interface violations)
- **Coverage Target**: 100% of DTO interfaces, 100% of AIPort methods
- **Test File Location**: `tests/contracts/test_ai_port_contract.py`, `tests/contracts/test_dto_schemas.py`

#### Tasks (TDD Workflow):

**RED - Write Failing Tests First**:
- [ ] Write `tests/contracts/test_ai_port_contract.py`
  - Test `AIPort.analyze()` requires `AnalysisRequest` DTO
  - Test `AIPort.analyze()` returns `TradingDecision` DTO
  - Test `TechnicalIndicators.from_dict()` handles all field types
  - Test `AnalysisRequest` rejects DataFrame (only accepts List[MarketData])
- [ ] Write `tests/contracts/test_dto_schemas.py`
  - Test `TechnicalIndicators` serialization (Dict ↔ DTO)
  - Test `TradingDecision` serialization (Dict ↔ DTO)
  - Test `MarketData.from_ohlcv()` type coercion
- [ ] Write `tests/contracts/test_openai_api_compatibility.py`
  - Test `OpenAIAdapter` uses `max_completion_tokens` (not `max_tokens`)
  - Test `OpenAIAdapter` handles API errors gracefully
  - Mock OpenAI API to simulate failures
- [ ] Run tests → **ALL SHOULD FAIL** (write tests before implementation)
- [ ] Commit failing tests with message: "RED: Add contract tests for AIPort interface"

**GREEN - Minimal Implementation**:
- [ ] Add runtime validation to `AnalyzeMarketUseCase.analyze()`:
  ```python
  if chart_data is not None and isinstance(chart_data, pd.DataFrame):
      raise TypeError(f"chart_data must be Dict or List, not DataFrame. Got: {type(chart_data)}")
  ```
- [ ] Add DTO validation helper: `src/application/dto/validation.py`:
  ```python
  def validate_technical_indicators(value) -> TechnicalIndicators:
      if isinstance(value, dict):
          return TechnicalIndicators.from_dict(value)
      elif isinstance(value, TechnicalIndicators):
          return value
      else:
          raise TypeError(f"Expected Dict or TechnicalIndicators, got {type(value)}")
  ```
- [ ] Update `AnalyzeMarketUseCase` to use validation helper
- [ ] Run tests → **ALL SHOULD PASS**
- [ ] Commit with message: "GREEN: Add DTO validation to prevent parameter errors"

**REFACTOR - Improve Code Quality**:
- [ ] Extract validation logic to dedicated module
- [ ] Add type hints to all UseCase methods
- [ ] Document DTO contracts in docstrings
- [ ] Run tests after each refactoring step
- [ ] Commit with message: "REFACTOR: Extract DTO validation to dedicated module"

**Quality Gate**:
- [ ] All contract tests pass
- [ ] `pytest tests/contracts/ -v` exits with 0
- [ ] Test coverage for DTOs ≥ 95%
- [ ] No `mypy` type errors in `src/application/`

**Dependencies**: None (this is first phase)

**Coverage Target**: 95% for DTO validation logic

---

### Phase 2: Extract Domain Logic from Legacy AI Code

**Goal**: Preserve business logic while eliminating legacy code

**Duration**: 2-3 hours

**Test Strategy**:
- **Test Type**: Unit tests for domain services
- **Coverage Target**: ≥ 90% for extracted logic
- **Test File Location**: `tests/unit/domain/services/test_market_analysis.py`

#### Tasks (TDD Workflow):

**RED - Write Failing Tests First**:
- [ ] Write `tests/unit/domain/services/test_market_analysis.py`
  - Test `calculate_market_beta()` (from `market_correlation.py`)
  - Test `calculate_alpha()` (from `market_correlation.py`)
  - Test edge cases (empty data, mismatched dates)
- [ ] Write `tests/unit/domain/services/test_trading_validation.py`
  - Test `validate_rsi_contradiction()` (from `validator.py`)
  - Test `validate_fakeout()` (from `validator.py`)
  - Test `validate_trend_filter()` (from `validator.py`)
- [ ] Run tests → **ALL SHOULD FAIL**
- [ ] Commit failing tests

**GREEN - Extract Logic**:
- [ ] Create `src/domain/services/market_analysis.py`
  - Extract `calculate_market_risk()` from `src/ai/market_correlation.py`
  - Make it pure function (no AI coupling)
- [ ] Update `ValidationAdapter` in `src/infrastructure/adapters/validation.py`
  - Extract validation rules from `src/ai/validator.py`
  - Implement `ValidationPort` interface
- [ ] Run tests → **ALL SHOULD PASS**
- [ ] Commit with message: "GREEN: Extract domain logic to dedicated services"

**REFACTOR - Remove Duplication**:
- [ ] Remove duplicated validation logic across adapters
- [ ] Consolidate market analysis functions
- [ ] Run tests after each refactoring step
- [ ] Commit with message: "REFACTOR: Consolidate domain services"

**Quality Gate**:
- [ ] All extracted logic has ≥90% test coverage
- [ ] `pytest tests/unit/domain/services/ -v` passes
- [ ] No circular dependencies
- [ ] Domain services have no infrastructure imports

**Dependencies**: Phase 1 (need DTOs validated)

**Coverage Target**: 90% for domain services

---

### Phase 3: Migrate All AI Calls to AIPort

**Goal**: Replace all legacy AI analyzer usage with Clean Architecture

**Duration**: 4-5 hours

**Test Strategy**:
- **Test Type**: Integration tests for pipeline stages
- **Coverage Target**: ≥ 80% for pipeline stages
- **Test File Location**: `tests/integration/test_pipeline_with_ai_port.py`

#### Tasks (TDD Workflow):

**RED - Write Failing Tests First**:
- [ ] Write `tests/integration/test_pipeline_with_ai_port.py`
  - Test `HybridRiskCheckStage` uses `AnalyzeMarketUseCase` (not `PositionAnalyzer`)
  - Test `CoinScanStage` uses `AnalyzeMarketUseCase` (not `EntryAnalyzer`)
  - Mock `Container.get_analyze_market_use_case()`
- [ ] Run tests → **ALL SHOULD FAIL**
- [ ] Commit failing tests

**GREEN - Update Pipeline Stages**:
- [ ] Update `src/trading/pipeline/hybrid_stage.py`:
  - Replace `PositionAnalyzer` with `ManagePositionUseCase` + `AnalyzeMarketUseCase`
  - Use `container.get_analyze_market_use_case()`
- [ ] Update `src/scanner/coin_selector.py`:
  - Replace `EntryAnalyzer` with `AnalyzeMarketUseCase`
  - Pass backtest results via `additional_context` parameter
- [ ] Update `src/container.py`:
  - Remove `EnhancedOpenAIAdapter` import from `get_analyze_breakout_use_case()`
  - Use `self.get_ai_port()` instead
- [ ] Run tests → **ALL SHOULD PASS**
- [ ] Commit with message: "GREEN: Migrate pipeline stages to AIPort"

**REFACTOR - Simplify Integration**:
- [ ] Remove duplicate AI call logic
- [ ] Consolidate context building for `AnalysisRequest`
- [ ] Run tests after each refactoring step
- [ ] Commit with message: "REFACTOR: Simplify AIPort integration"

**Quality Gate**:
- [ ] All pipeline stages use `AIPort` exclusively
- [ ] `grep -r "EntryAnalyzer\|PositionAnalyzer\|EnhancedOpenAIAdapter" src/trading/ src/scanner/` returns no results
- [ ] `pytest tests/integration/ -v` passes
- [ ] Manual test: Run `python main.py` successfully

**Dependencies**: Phase 2 (need domain services extracted)

**Coverage Target**: 80% for pipeline integration

**Rollback Strategy**:
- Keep legacy code in separate branch
- Revert commits if integration breaks
- Manual fallback: Restore `EntryAnalyzer` imports temporarily

---

### Phase 4: Delete Legacy Code

**Goal**: Remove all legacy AI code to prevent confusion

**Duration**: 1-2 hours

**Test Strategy**:
- **Test Type**: Full test suite (ensure nothing breaks)
- **Coverage Target**: No coverage loss after deletion
- **Test File Location**: All existing tests

#### Tasks (TDD Workflow):

**RED - Verify Tests Pass Before Deletion**:
- [ ] Run full test suite: `pytest tests/ -v`
  - **ALL MUST PASS** before deletion
- [ ] Document current test pass rate
- [ ] Commit with message: "Checkpoint before legacy code deletion"

**GREEN - Delete Legacy Code**:
- [ ] Delete `src/ai/entry_analyzer.py`
- [ ] Delete `src/ai/position_analyzer.py`
- [ ] Delete `src/ai/validator.py` (logic moved to `ValidationPort`)
- [ ] Delete `src/ai/market_correlation.py` (logic moved to domain service)
- [ ] Delete `src/ai/__init__.py`
- [ ] Delete `src/infrastructure/adapters/ai/enhanced_openai_adapter.py`
- [ ] Remove `src/ai/` directory entirely
- [ ] Update all imports (search for `from src.ai.`)
- [ ] Run full test suite → **ALL SHOULD STILL PASS**
- [ ] Commit with message: "GREEN: Delete legacy AI code"

**REFACTOR - Clean Up Imports**:
- [ ] Search and replace all legacy imports
- [ ] Remove unused test mocks
- [ ] Update `__init__.py` files
- [ ] Run tests after each cleanup step
- [ ] Commit with message: "REFACTOR: Clean up imports after legacy deletion"

**Quality Gate**:
- [ ] `ls src/ai/` returns "No such file or directory"
- [ ] `grep -r "from src.ai." src/` returns no results
- [ ] `pytest tests/ -v` exits with 0
- [ ] Test coverage maintained or improved
- [ ] No import errors

**Dependencies**: Phase 3 (all usages must be migrated first)

**Coverage Target**: Maintain current coverage (no loss)

**Rollback Strategy**:
- Git revert to commit before deletion
- Restore `src/ai/` from previous commit
- Re-run tests to verify restoration

---

### Phase 5: Documentation Update

**Goal**: Ensure all documentation matches current reality

**Duration**: 3-4 hours

**Test Strategy**:
- **Test Type**: Documentation validation (manual review + automated checks)
- **Coverage Target**: 100% of modified docs reviewed
- **Validation**: Links work, code examples compile, architecture diagrams match code

#### Tasks:

- [ ] Update `docs/guide/ARCHITECTURE.md`:
  - **DELETE** sections about `src/ai/` legacy structure (line 139-145)
  - **ADD** Clean Architecture AI flow diagram
  - **UPDATE** component descriptions to reflect `AIPort` usage
  - **ADD** section on Contract Tests
- [ ] Update `docs/guide/USER_GUIDE.md`:
  - Remove references to `EntryAnalyzer` / `PositionAnalyzer`
  - Update code examples to use `Container.get_ai_port()`
- [ ] Create `docs/guide/AI_ARCHITECTURE.md`:
  - Document `AIPort` interface contract
  - Document `OpenAIAdapter` implementation
  - Document DTO schemas (`AnalysisRequest`, `TradingDecision`)
  - Add examples of how to call AI analysis
- [ ] Update `docs/diagrams/`:
  - Update `03-trading-execution-flow.mmd` to show `AIPort` flow
  - Update `10-clean-architecture.mmd` to remove legacy AI references
- [ ] Update `CLAUDE.md`:
  - Add section on Contract Tests (mandatory)
  - Add section on DTO validation requirements
  - Update architectural layers to show domain services
- [ ] Create `docs/decisions/ADR-005-ai-clean-architecture.md`:
  - Document decision to use AIPort exclusively
  - Document rationale for eliminating legacy code
  - Document lessons learned from parameter errors

**Quality Gate**:
- [ ] All links in docs work (no 404s)
- [ ] All code examples are valid Python
- [ ] Architecture diagrams match actual code structure
- [ ] `grep -r "EntryAnalyzer\|PositionAnalyzer\|src/ai/" docs/` returns no results (except in migration guides)
- [ ] Manual review: Read through ARCHITECTURE.md and verify accuracy

**Dependencies**: Phase 4 (code must be deleted first)

**Rollback Strategy**:
- Git revert documentation changes
- Restore previous versions from git history

---

### Phase 6: Final Validation & Testing

**Goal**: Ensure entire system works end-to-end with no regressions

**Duration**: 2-3 hours

**Test Strategy**:
- **Test Type**: End-to-end integration tests + manual QA
- **Coverage Target**: ≥ 85% overall code coverage
- **Test File Location**: `tests/e2e/test_full_trading_cycle.py`

#### Tasks:

**Integration Tests**:
- [ ] Write `tests/e2e/test_full_trading_cycle.py`:
  - Test complete trading cycle (scan → analyze → execute)
  - Mock Upbit API, OpenAI API
  - Verify AIPort used throughout
- [ ] Run full test suite with coverage:
  ```bash
  pytest tests/ --cov=src --cov=backend --cov-report=html --cov-report=term
  ```
- [ ] Verify coverage ≥ 85%

**Manual QA**:
- [ ] Run scheduler in Docker:
  ```bash
  docker-compose build --no-cache
  docker-compose up -d scheduler
  docker-compose logs -f scheduler
  ```
- [ ] Verify trading_job executes without errors
- [ ] Verify AI analysis produces Korean responses
- [ ] Verify no parameter errors in logs
- [ ] Check Telegram notifications work
- [ ] Check Grafana dashboard shows correct data

**Performance Validation**:
- [ ] Measure AI call latency (should be < 5s)
- [ ] Verify no memory leaks (run for 1 hour)
- [ ] Check rate limiting works (no 429 errors)

**Quality Gate**:
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Overall coverage ≥ 85%
- [ ] E2E test completes successfully
- [ ] Manual trading cycle works without errors
- [ ] No parameter errors in logs for 1 hour run
- [ ] Grafana shows correct metrics

**Dependencies**: Phase 5 (docs must be updated)

**Coverage Target**: 85% overall

**Rollback Strategy**:
- If manual QA fails, revert all changes
- Restore backup from Phase 0 checkpoint
- Document failure reason for future attempts

---

## 🚨 Risk Assessment

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Breaking existing trading logic | Medium | **High** | Write contract tests first (Phase 1), comprehensive integration tests (Phase 6) |
| Missing edge cases in DTO validation | Medium | Medium | Add fuzzing tests, test with production data samples |
| Performance degradation from validation overhead | Low | Medium | Benchmark before/after, optimize validation logic if needed |
| Incomplete legacy code removal | Low | High | Use grep to find all usages, automate search |

### Dependency Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| OpenAI API changes during migration | Low | High | Pin API version in tests, use mocks |
| Docker build fails after deletion | Low | Medium | Test Docker build in Phase 4 |

### Timeline Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Testing takes longer than expected | Medium | Low | Prioritize contract tests, skip less critical tests if needed |
| Documentation update scope creep | Medium | Low | Focus on critical docs first (ARCHITECTURE.md) |

---

## 🔄 Rollback Strategy

### Per-Phase Rollback

Each phase can be rolled back independently by reverting commits:

```bash
# Rollback Phase N
git log --oneline  # Find commit before Phase N
git revert <commit-hash>..HEAD
```

### Emergency Rollback (Full)

If multiple phases break production:

```bash
# Create backup branch before starting
git checkout -b backup-before-ai-migration

# After phases, if disaster occurs:
git checkout main
git reset --hard backup-before-ai-migration
git push --force-with-lease
```

### Validation After Rollback

- [ ] Run full test suite
- [ ] Verify trading cycle works
- [ ] Check logs for errors
- [ ] Notify team of rollback reason

---

## 📝 Progress Tracking

### Phase Completion Checklist

- [ ] Phase 1: Contract Tests & Type Safety
- [ ] Phase 2: Extract Domain Logic
- [ ] Phase 3: Migrate All AI Calls to AIPort
- [ ] Phase 4: Delete Legacy Code
- [ ] Phase 5: Documentation Update
- [ ] Phase 6: Final Validation & Testing

### Metrics

**Test Coverage**:
- Before: __%
- After Phase 1: __%
- After Phase 6: ≥85%

**Legacy Code Lines**:
- Before: ~2000 lines (src/ai/ + enhanced_openai_adapter.py)
- After Phase 4: 0 lines

**Parameter Errors**:
- Before: 5+ errors in last 3 sessions
- After Phase 1: 0 errors (contract tests prevent)

---

## 📚 Notes & Learnings

### Key Insights

_(Document learnings as you complete phases)_

- **Phase 1**:
- **Phase 2**:
- **Phase 3**:
- **Phase 4**:
- **Phase 5**:
- **Phase 6**:

### Challenges Encountered

_(Document unexpected issues)_

### Future Improvements

_(What would make this better next time?)_

---

## ✅ Definition of Done

This migration is **DONE** only when ALL conditions are met:

- [ ] All 6 phases completed
- [ ] All quality gates passed
- [ ] `src/ai/` directory deleted
- [ ] `enhanced_openai_adapter.py` deleted
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Overall test coverage ≥ 85%
- [ ] E2E test passes
- [ ] Manual trading cycle works without errors
- [ ] No parameter errors in 1-hour run
- [ ] Documentation updated (ARCHITECTURE.md, USER_GUIDE.md, AI_ARCHITECTURE.md)
- [ ] Documentation governance completed (see below)
- [ ] `grep -r "EntryAnalyzer\|PositionAnalyzer\|from src.ai." src/` returns no results
- [ ] Docker build succeeds
- [ ] Grafana shows correct metrics

⛔ **Skipping documentation governance invalidates feature completion.**

---

## 🗂 Documentation Governance (Post-Completion)

### Actions After All Phases Complete

#### 1. Docs Inventory

- [ ] Scan `docs/` directory for all `.md` files
- [ ] Classify each file:
  - `ACTIVE` - Accurate and current
  - `UPDATE` - Partially outdated (needs revision)
  - `DELETE` - Obsolete or misleading

#### 2. Planning Docs Resolution

- [ ] Extract key decisions from this plan into:
  - `docs/decisions/ADR-005-ai-clean-architecture.md`
- [ ] Archive this plan to: `docs/plans/archive/PLAN_ai_legacy_elimination_clean_architecture.md`
- [ ] Update `docs/plans/README.md` to mark this plan as **COMPLETED**

#### 3. Docs vs Code Validation

- [ ] Validate `docs/guide/ARCHITECTURE.md` against:
  - Current `src/` structure
  - Actual pipeline flow
  - Container dependency wiring
- [ ] Validate `docs/guide/USER_GUIDE.md` code examples compile
- [ ] Validate all diagrams in `docs/diagrams/` match code

#### 4. Canonical Docs Update

- [ ] Ensure `ARCHITECTURE.md` is singular source of truth
- [ ] Remove duplicate architecture descriptions from other docs
- [ ] Normalize terminology (e.g., always "AIPort", never "AI Service")

#### 5. Enforcement Actions

- [ ] Delete obsolete docs:
  - [ ] `docs/guide/MIGRATION_AI_CLEAN_ARCHITECTURE.md` (migration complete)
  - [ ] Any docs referencing `EntryAnalyzer` / `PositionAnalyzer`
- [ ] Update outdated sections (remove "will / planned" language)
- [ ] Merge duplicate docs if found

#### 6. Documentation Change Log

Create `docs/CHANGELOG_AI_MIGRATION_DOCS.md`:

```markdown
# Documentation Changes - AI Clean Architecture Migration

**Date**: 2026-01-04

## Deleted Files

- `docs/guide/MIGRATION_AI_CLEAN_ARCHITECTURE.md` - Migration complete, no longer needed

## Updated Files

- `docs/guide/ARCHITECTURE.md` - Removed legacy `src/ai/` references, added AIPort flow
- `docs/guide/USER_GUIDE.md` - Updated code examples to use AIPort
- `docs/diagrams/03-trading-execution-flow.mmd` - Updated to show Clean Architecture flow

## Created Files

- `docs/guide/AI_ARCHITECTURE.md` - Comprehensive AIPort documentation
- `docs/decisions/ADR-005-ai-clean-architecture.md` - Architectural decision record

## Archived Files

- `docs/plans/PLAN_ai_legacy_elimination_clean_architecture.md` → `docs/plans/archive/`
```

---

## 🎯 Success Metrics

**Quantitative**:
- ✅ 0 legacy AI code lines remaining
- ✅ Test coverage ≥ 85%
- ✅ 0 parameter errors in 1-hour run
- ✅ 100% of docs updated

**Qualitative**:
- ✅ Developers can confidently modify AI logic
- ✅ New contributors understand architecture from docs
- ✅ Trading pipeline is reliable and maintainable

---

**END OF PLAN**
