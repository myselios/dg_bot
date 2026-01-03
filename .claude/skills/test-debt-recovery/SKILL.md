---
name: test-debt-recovery
description: Restores TDD discipline and raises test coverage safely via incremental, risk-driven refactoring. Creates a measurable recovery plan, adds characterization tests first, then refactors under coverage and reliability gates.
use_when: coverage drops, TDD not followed, refactor needed, flaky tests, large changes merged, confidence degraded
---

# Test Debt Recovery Skill

## Purpose

This skill is used when **TDD discipline and coverage have degraded** and the team is paying “confidence tax”:
- Fear of changes
- Frequent hotfixes
- Large refactor cycles
- Unclear ownership of critical paths

Goals:
- Recover **test-first habits** (Red → Green → Refactor)
- Increase **meaningful coverage** (not cosmetic)
- Reduce **flakiness** and improve reliability
- Refactor safely under tests, without breaking trading behavior

---

## Core Principles (Non-Negotiable)

1. **Characterize before refactor**
   - If behavior is unclear, write tests that capture current behavior first.
2. **Risk-driven coverage**
   - Target code that can lose money / place orders / manage risk first.
3. **Incremental delivery**
   - Every phase ends with a runnable state and measurable gains.
4. **No “coverage theater”**
   - Coverage must correlate with risk reduction (critical paths, invariants, boundaries).

---

## Scope Sizing

Choose one scope for a recovery run:

- **Small (1–3 hours)**: One module / one pipeline stage / one adapter boundary
- **Medium (4–8 hours)**: A full pipeline slice (Data→Analysis→Execution) or scheduler subsystem
- **Large (multi-day)**: Entire system recovery (not recommended unless project is already unstable)

⛔ Default: Start Small. Repeat weekly instead of doing massive cleanups.

---

## Recovery Workflow (3–6 Phases)

Each phase must be **1–4 hours max** and follow Red-Green-Refactor.

### Phase 0: Baseline & Target Selection (≤1 hour)
**Goal**
- Establish current reality (coverage, flaky tests, risk hot spots)
- Select a focused target slice for recovery

**Tasks**
- [ ] Run full test suite:
  - `python -m pytest tests/ -v`
- [ ] Capture coverage baseline:
  - `python -m pytest tests/ --cov=src --cov=backend --cov-report=term-missing`
- [ ] Identify top risk areas (choose 1–2 only):
  - Order execution (`ExecuteTradeUseCase`, exchange adapter)
  - Position management (stop loss / take profit rules)
  - Scheduler job boundaries (duplicate prevention, idempotency)
  - AI decision boundary (prompt → decision parsing → execution)
  - Persistence/logging correctness (trade logs, ai_decision logs)

**Quality Gate**
- [ ] Baseline recorded in `docs/CHANGELOG_TEST_DEBT.md`
- [ ] Target slice defined (paths/modules/functions)

**Coverage Target**
- Baseline measured (no improvement required in Phase 0)

**Rollback**
- No code changes required; only measurement artifacts.

---

### Phase 1: Characterization Tests (RED first) (1–4 hours)
**Goal**
- Create tests that lock current behavior for the chosen slice (“safety harness”)

**Test Strategy**
- Unit tests for deterministic business logic (≥80% for target slice)
- Integration tests for boundaries (ports/adapters, scheduler, DB where critical)
- Emphasize **invariants** and **edge cases**:
  - “Never buy if already holding”
  - “Never sell below min trade”
  - “Stop loss triggers exactly once”
  - “Scheduler does not run concurrently (idempotency)”
  - “AI decision parse failure fails safe”

**Tasks**
- [ ] **RED**: Write failing tests first for:
  - Happy path (expected behavior)
  - Edge path (missing data / partial OHLCV / API timeout)
  - Safety path (no-trade conditions, risk constraints)
- [ ] Ensure failures are for the right reasons (assertions, not setup errors)
- [ ] Create fixtures/mocks for:
  - ExchangePort
  - AIPort
  - MarketDataPort
  - Time control (freezegun or custom clock abstraction if used)

**Quality Gate**
- [ ] Tests fail for correct reasons (before implementation)
- [ ] No real network calls in unit tests
- [ ] Test runtime remains <5 minutes for full suite

**Coverage Target**
- [ ] Target slice +10% absolute coverage OR ≥70% line coverage within slice (whichever is smaller but measurable)

**Rollback**
- Revert tests only if they are flaky or rely on external state.

---

### Phase 2: Make Tests Pass (GREEN) (1–4 hours)
**Goal**
- Minimal code changes to satisfy characterization tests and close obvious gaps

**Tasks**
- [ ] **GREEN**: Implement minimal fixes only where tests require
- [ ] Add safe default behaviors (fail-safe) where ambiguity exists:
  - parsing errors → HOLD
  - missing indicators → HOLD
  - external API instability → no trade + log
- [ ] Run:
  - `python -m pytest tests/ -v`
  - coverage command again

**Quality Gate**
- [ ] All tests green
- [ ] No new flaky tests
- [ ] Coverage improved vs baseline for the target slice
- [ ] No behavioral regressions (manual sanity: one dry-run cycle if applicable)

**Coverage Target**
- [ ] Meet Phase 1 target (slice coverage threshold)

**Rollback**
- Revert minimal changes; keep tests if they represent valid safety expectations.

---

### Phase 3: Refactor Under Tests (REFACTOR) (1–4 hours)
**Goal**
- Improve structure while maintaining behavior and test safety net

**Refactor Priorities (pick 1–2)**
- Extract pure functions for business rules (domain/application)
- Separate IO (adapters) from logic (use cases)
- Reduce hidden coupling and global state
- Make scheduler job logic deterministic and testable (inject clock/config)
- Introduce clear boundaries: parsing/validation/execution

**Tasks**
- [ ] **REFACTOR**: Apply small refactors in tiny commits
- [ ] After each change:
  - run targeted tests
  - then run full suite
- [ ] Remove dead code / duplicated logic discovered during refactor

**Quality Gate**
- [ ] Tests stay green after each refactor step
- [ ] Complexity reduced (measurable: fewer branches / clearer boundaries)
- [ ] No change to trade safety invariants

**Coverage Target**
- [ ] Maintain or increase coverage (no decrease allowed)

**Rollback**
- Roll back refactor commit(s) while preserving tests.

---

### Phase 4: Flakiness & Reliability Hardening (Optional, 1–4 hours)
**Goal**
- Stabilize the suite and prevent future TDD erosion

**Tasks**
- [ ] Identify flaky tests by re-running:
  - `python -m pytest tests/ -v` (2–3 times)
- [ ] Fix common sources:
  - time dependence → fake clock / freeze time
  - randomness → seed control
  - shared state → isolate fixtures
  - async/scheduler timing → deterministic triggers, avoid real APScheduler in unit tests
- [ ] Add “contract tests” for ports/adapters (mock expectations)

**Quality Gate**
- [ ] No flakes across 3 consecutive runs
- [ ] Suite time <5 minutes (or justified)

**Coverage Target**
- [ ] Not required; stability is the goal

**Rollback**
- Revert unstable test approach; prefer deterministic boundaries.

---

## Global Quality Gates (Blocking)

**Build & Tests**
- [ ] `python -m pytest tests/ -v` passes
- [ ] No new failing or skipped tests without justification

**Coverage**
- [ ] Coverage does not decrease globally
- [ ] Target slice coverage increases measurably
- [ ] Business logic ≥80% within slice OR documented reason why not

**TDD Compliance**
- [ ] New behavior: tests written before code
- [ ] Refactor: tests remain green throughout

**Safety Invariants**
- [ ] No rule allows unintended order placement
- [ ] Failure modes default to HOLD / NO-TRADE

**Docs**
- [ ] Update `docs/CHANGELOG_TEST_DEBT.md` with:
  - baseline
  - targets
  - outcomes
  - learnings

---

## Reporting Artifacts

Create/update:
- `docs/CHANGELOG_TEST_DEBT.md`
  - Date
  - Baseline coverage
  - Target slice
  - Coverage delta
  - Flakiness notes
  - Follow-ups

Optional:
- `docs/TESTING_STRATEGY.md` (if missing)
  - What is unit vs integration vs e2e in this repo
  - Where mocks are allowed
  - Port/adapters contract test rules

---

## Prevention Protocol (Recommended)

After recovery, enforce:
- “No PR merge if coverage drops” (soft/hard threshold)
- “Every new feature must include tests in same commit”
- “Weekly small-scope Test Debt Recovery run” (1–3 hours)

---

## Definition of Done

A recovery run is DONE when:
- Coverage baseline is recorded
- Target slice coverage increased
- Tests are stable and green
- Refactor completed without behavior drift
- Safety invariants are explicitly tested
