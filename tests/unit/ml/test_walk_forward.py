"""
WalkForwardValidator 테스트

Phase 5: Walk-Forward Validation (누수 방지)
- Purge 구간 (Train-Validate 사이 버퍼)
- Embargo 구간 (Validate-Test 사이 버퍼)
- 코인 간 동시성 누수 방지
- Hold-out 구간 보호
"""

import pytest
from datetime import datetime, timedelta
from typing import List

import pandas as pd
import numpy as np


class TestLeakagePreventionConfig:
    """LeakagePreventionConfig 테스트"""

    def test_default_purge_days(self):
        """기본 Purge는 7일이어야 한다"""
        from src.ml.walk_forward import LeakagePreventionConfig

        config = LeakagePreventionConfig()
        assert config.purge_days == 7

    def test_default_embargo_days(self):
        """기본 Embargo는 3일이어야 한다"""
        from src.ml.walk_forward import LeakagePreventionConfig

        config = LeakagePreventionConfig()
        assert config.embargo_days == 3

    def test_default_holdout_months(self):
        """기본 Hold-out은 3개월이어야 한다"""
        from src.ml.walk_forward import LeakagePreventionConfig

        config = LeakagePreventionConfig()
        assert config.holdout_months == 3

    def test_validate_purge_minimum(self):
        """Purge는 최소 7일이어야 한다"""
        from src.ml.walk_forward import LeakagePreventionConfig

        # 유효
        config = LeakagePreventionConfig(purge_days=7)
        assert config.validate() is True

        # 무효 (7일 미만)
        with pytest.raises(AssertionError):
            config = LeakagePreventionConfig(purge_days=5)
            config.validate()

    def test_validate_embargo_minimum(self):
        """Embargo는 최소 3일이어야 한다"""
        from src.ml.walk_forward import LeakagePreventionConfig

        # 유효
        config = LeakagePreventionConfig(embargo_days=3)
        assert config.validate() is True

        # 무효 (3일 미만)
        with pytest.raises(AssertionError):
            config = LeakagePreventionConfig(embargo_days=2)
            config.validate()


class TestWalkForwardValidator:
    """WalkForwardValidator 테스트"""

    def test_purge_gap_exists(self):
        """Train-Validate 사이에 Purge 구간이 있어야 한다"""
        from src.ml.walk_forward import WalkForwardValidator, LeakagePreventionConfig

        config = LeakagePreventionConfig(purge_days=7)
        validator = WalkForwardValidator(config)

        # 테스트 데이터 생성
        dates = pd.date_range('2024-01-01', '2024-12-31', freq='D')
        data = pd.DataFrame({
            'date': dates,
            'close': np.random.randn(len(dates)) + 100,
        })

        folds = validator.split(data)

        for fold in folds:
            # Purge 구간이 존재해야 함
            assert fold.purge is not None
            purge_start, purge_end = fold.purge

            # Purge 기간이 최소 7일
            purge_days = (purge_end - purge_start).days
            assert purge_days >= 7, f"Purge 기간 부족: {purge_days}일"

            # Train 끝 <= Purge 시작
            assert fold.train[1] <= purge_start

            # Purge 끝 <= Validate 시작
            assert purge_end <= fold.validate[0]

    def test_embargo_gap_exists(self):
        """Validate 후에 Embargo 구간이 있어야 한다"""
        from src.ml.walk_forward import WalkForwardValidator, LeakagePreventionConfig

        config = LeakagePreventionConfig(embargo_days=3)
        validator = WalkForwardValidator(config)

        dates = pd.date_range('2024-01-01', '2024-12-31', freq='D')
        data = pd.DataFrame({
            'date': dates,
            'close': np.random.randn(len(dates)) + 100,
        })

        folds = validator.split(data)

        for fold in folds:
            # Embargo 구간이 존재해야 함
            assert fold.embargo is not None
            embargo_start, embargo_end = fold.embargo

            # Embargo 기간이 최소 3일
            embargo_days = (embargo_end - embargo_start).days
            assert embargo_days >= 3, f"Embargo 기간 부족: {embargo_days}일"

            # Validate 끝 <= Embargo 시작
            assert fold.validate[1] <= embargo_start

    def test_no_cross_coin_leakage(self):
        """코인 간 시간 구간이 중복되지 않아야 한다"""
        from src.ml.walk_forward import WalkForwardValidator, LeakagePreventionConfig

        config = LeakagePreventionConfig()
        validator = WalkForwardValidator(config)

        dates = pd.date_range('2024-01-01', '2024-12-31', freq='D')
        data = pd.DataFrame({
            'date': dates,
            'close': np.random.randn(len(dates)) + 100,
        })

        folds = validator.split(data)

        for fold in folds:
            train_dates = set(
                pd.date_range(fold.train[0], fold.train[1], freq='D')
            )
            validate_dates = set(
                pd.date_range(fold.validate[0], fold.validate[1], freq='D')
            )

            # Train과 Validate 날짜가 겹치면 안됨
            overlap = train_dates & validate_dates
            assert len(overlap) == 0, f"시간 구간 중복: {len(overlap)}일"

    def test_holdout_never_used_for_training(self):
        """Hold-out 구간은 학습에 사용되지 않아야 한다"""
        from src.ml.walk_forward import WalkForwardValidator, LeakagePreventionConfig

        config = LeakagePreventionConfig(holdout_months=3)
        validator = WalkForwardValidator(config)

        # 24개월 데이터
        dates = pd.date_range('2024-01-01', '2025-12-31', freq='D')
        data = pd.DataFrame({
            'date': dates,
            'close': np.random.randn(len(dates)) + 100,
        })

        folds = validator.split(data)

        # Hold-out 시작점 (마지막 3개월 시작)
        holdout_start = dates[-1] - timedelta(days=90)

        for fold in folds:
            train_end = fold.train[1]
            # Train이 Hold-out 구간에 들어가면 안됨
            assert train_end < holdout_start, f"Hold-out 침범: {train_end}"


class TestFold:
    """Fold 데이터 구조 테스트"""

    def test_fold_has_required_fields(self):
        """Fold는 필수 필드를 가져야 한다"""
        from src.ml.walk_forward import Fold

        fold = Fold(
            train=(datetime(2024, 1, 1), datetime(2024, 6, 30)),
            purge=(datetime(2024, 6, 30), datetime(2024, 7, 7)),
            validate=(datetime(2024, 7, 7), datetime(2024, 9, 30)),
            embargo=(datetime(2024, 9, 30), datetime(2024, 10, 3)),
        )

        assert fold.train is not None
        assert fold.purge is not None
        assert fold.validate is not None
        assert fold.embargo is not None

    def test_fold_dates_are_ordered(self):
        """Fold의 날짜는 순서대로여야 한다"""
        from src.ml.walk_forward import Fold

        fold = Fold(
            train=(datetime(2024, 1, 1), datetime(2024, 6, 30)),
            purge=(datetime(2024, 6, 30), datetime(2024, 7, 7)),
            validate=(datetime(2024, 7, 7), datetime(2024, 9, 30)),
            embargo=(datetime(2024, 9, 30), datetime(2024, 10, 3)),
        )

        # 순서 확인: Train < Purge < Validate < Embargo
        assert fold.train[1] <= fold.purge[0]
        assert fold.purge[1] <= fold.validate[0]
        assert fold.validate[1] <= fold.embargo[0]


class TestCrossCoinLeakageCheck:
    """코인 간 누수 검사 테스트"""

    def test_detect_cross_coin_leakage(self):
        """코인 간 누수를 감지해야 한다"""
        from src.ml.walk_forward import prevent_cross_coin_leakage, LeakageError

        # 중복 날짜가 있는 경우
        train_data = pd.DataFrame({
            'date': pd.date_range('2024-01-01', '2024-06-30', freq='D'),
        })
        validate_data = pd.DataFrame({
            'date': pd.date_range('2024-06-01', '2024-09-30', freq='D'),  # 겹침
        })

        with pytest.raises(LeakageError):
            prevent_cross_coin_leakage(train_data, validate_data)

    def test_no_leakage_when_dates_separate(self):
        """날짜가 분리되어 있으면 누수가 없다"""
        from src.ml.walk_forward import prevent_cross_coin_leakage

        # 겹치지 않는 경우
        train_data = pd.DataFrame({
            'date': pd.date_range('2024-01-01', '2024-06-30', freq='D'),
        })
        validate_data = pd.DataFrame({
            'date': pd.date_range('2024-07-08', '2024-09-30', freq='D'),
        })

        # 예외 없이 통과
        result = prevent_cross_coin_leakage(train_data, validate_data)
        assert result is True
