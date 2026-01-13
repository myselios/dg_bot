"""
WalkForwardValidator - 누수 방지가 적용된 Walk-Forward Validation

Purge: Train-Validate 사이 버퍼 (최소 7일)
Embargo: Validate 후 버퍼 (최소 3일)
Hold-out: 최종 평가 전용 (학습 금지)
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Set

import pandas as pd

logger = logging.getLogger(__name__)


class LeakageError(Exception):
    """데이터 누수 탐지 오류"""
    pass


@dataclass
class LeakagePreventionConfig:
    """
    누수 방지 설정

    Attributes:
        purge_days: Train-Validate 사이 버퍼 (기본 7일)
        embargo_days: Validate-Test 사이 버퍼 (기본 3일)
        holdout_months: 최종 평가 전용 구간 (기본 3개월)
        same_period_reuse: 동일 시간 구간 재사용 허용 여부
    """

    purge_days: int = 7
    embargo_days: int = 3
    holdout_months: int = 3
    same_period_reuse: bool = False

    def validate(self) -> bool:
        """
        누수 방지 설정 검증

        Raises:
            AssertionError: 설정이 최소 요구사항을 충족하지 않을 때
        """
        assert self.purge_days >= 7, f"Purge는 최소 7일: {self.purge_days}"
        assert self.embargo_days >= 3, f"Embargo는 최소 3일: {self.embargo_days}"
        assert self.holdout_months >= 3, f"Hold-out은 최소 3개월: {self.holdout_months}"
        return True


@dataclass
class Fold:
    """
    Walk-Forward Fold 구조

    Attributes:
        train: 학습 구간 (시작, 종료)
        purge: Purge 구간 (시작, 종료)
        validate: 검증 구간 (시작, 종료)
        embargo: Embargo 구간 (시작, 종료)
    """

    train: Tuple[datetime, datetime]
    purge: Tuple[datetime, datetime]
    validate: Tuple[datetime, datetime]
    embargo: Tuple[datetime, datetime]

    def __post_init__(self):
        """날짜 순서 검증"""
        assert self.train[0] <= self.train[1], "Train 날짜 순서 오류"
        assert self.purge[0] <= self.purge[1], "Purge 날짜 순서 오류"
        assert self.validate[0] <= self.validate[1], "Validate 날짜 순서 오류"
        assert self.embargo[0] <= self.embargo[1], "Embargo 날짜 순서 오류"


class WalkForwardValidator:
    """
    누수 방지가 적용된 Walk-Forward Validator

    데이터 누수를 방지하기 위해:
    1. Purge 구간으로 Train-Validate 분리
    2. Embargo 구간으로 Validate-다음Fold 분리
    3. Hold-out 구간은 학습에 절대 사용 금지
    4. 코인 간 동시성 누수 검증
    """

    def __init__(self, config: LeakagePreventionConfig = None):
        """
        Args:
            config: 누수 방지 설정
        """
        self.config = config or LeakagePreventionConfig()
        self.config.validate()

    def split(
        self,
        data: pd.DataFrame,
        train_months: int = 6,
        validate_months: int = 3,
        step_months: int = 3,
    ) -> List[Fold]:
        """
        데이터를 Walk-Forward Fold로 분할

        Args:
            data: 분할할 데이터 (date 컬럼 필수)
            train_months: 학습 기간 (월)
            validate_months: 검증 기간 (월)
            step_months: 롤링 스텝 (월)

        Returns:
            Fold 리스트
        """
        dates = pd.to_datetime(data['date'])
        start_date = dates.min()
        end_date = dates.max()

        # Hold-out 시작점 계산 (마지막 N개월 제외)
        holdout_start = end_date - timedelta(days=self.config.holdout_months * 30)

        folds = []
        current_train_start = start_date

        while True:
            # Train 종료
            train_end = current_train_start + timedelta(days=train_months * 30)

            # Train이 Hold-out에 침범하면 중단
            if train_end >= holdout_start:
                break

            # Purge 구간
            purge_start = train_end
            purge_end = purge_start + timedelta(days=self.config.purge_days)

            # Validate 시작
            validate_start = purge_end
            validate_end = validate_start + timedelta(days=validate_months * 30)

            # Validate가 Hold-out에 침범하면 조정
            if validate_end > holdout_start:
                validate_end = holdout_start

            # Embargo 구간
            embargo_start = validate_end
            embargo_end = embargo_start + timedelta(days=self.config.embargo_days)

            # 유효한 Fold인지 확인
            if validate_start < validate_end:
                fold = Fold(
                    train=(current_train_start, train_end),
                    purge=(purge_start, purge_end),
                    validate=(validate_start, validate_end),
                    embargo=(embargo_start, embargo_end),
                )
                folds.append(fold)

            # 다음 Fold로 이동
            current_train_start = current_train_start + timedelta(days=step_months * 30)

            # 더 이상 유효한 Fold 생성 불가
            if current_train_start + timedelta(days=train_months * 30) >= holdout_start:
                break

        logger.info(f"Walk-Forward Split: {len(folds)} folds 생성")
        return folds

    def verify_no_cross_coin_leakage(
        self, fold: Fold, data: pd.DataFrame
    ) -> bool:
        """
        코인 간 시간 구간 중복 검증

        Args:
            fold: 검증할 Fold
            data: 데이터

        Returns:
            누수 없음 여부

        Raises:
            LeakageError: 누수 발견 시
        """
        dates = pd.to_datetime(data['date'])

        train_dates = set(
            dates[(dates >= fold.train[0]) & (dates <= fold.train[1])]
        )
        validate_dates = set(
            dates[(dates >= fold.validate[0]) & (dates <= fold.validate[1])]
        )

        overlap = train_dates & validate_dates
        if overlap:
            raise LeakageError(
                f"Cross-coin leakage detected: {len(overlap)} days overlap"
            )

        return True


def prevent_cross_coin_leakage(
    train_data: pd.DataFrame,
    validate_data: pd.DataFrame,
) -> bool:
    """
    코인 간 동시성 누수 방지 검증

    문제: 같은 시간대에 BTC로 학습하고 ETH로 검증하면
          시장 전체 움직임이 누수됨

    해결: 동일 시간 구간은 다른 코인에서도 재사용 금지

    Args:
        train_data: 학습 데이터 (date 컬럼 필수)
        validate_data: 검증 데이터 (date 컬럼 필수)

    Returns:
        누수 없음 여부

    Raises:
        LeakageError: 시간 구간 중복 발견 시
    """
    train_dates = set(pd.to_datetime(train_data['date']).unique())
    validate_dates = set(pd.to_datetime(validate_data['date']).unique())

    overlap = train_dates & validate_dates
    if overlap:
        min_date = min(overlap)
        max_date = max(overlap)
        raise LeakageError(
            f"시간 구간 중복 발견: {len(overlap)}일 "
            f"({min_date.strftime('%Y-%m-%d')} ~ {max_date.strftime('%Y-%m-%d')})"
        )

    return True
