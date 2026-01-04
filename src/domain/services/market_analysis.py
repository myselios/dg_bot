"""
시장 분석 도메인 서비스.

CAPM 모델 기반 베타/알파 계산 등 순수 비즈니스 로직을 제공합니다.
AI 커플링 없이 순수 함수로 구현되어 있습니다.

이 모듈은 src/ai/market_correlation.py에서 추출한 로직입니다.
"""
import pandas as pd
import numpy as np
from typing import Tuple


def calculate_market_beta(
    market_data: pd.DataFrame,
    asset_data: pd.DataFrame,
    lookback_days: int = 30
) -> float:
    """
    CAPM 모델 기반 베타 계산.

    베타(Beta): 자산이 시장 대비 얼마나 민감하게 반응하는지 측정
    - 베타 > 1.2: 자산이 시장보다 1.2배 민감
    - 베타 < 0.8: 자산이 시장보다 덜 민감

    Args:
        market_data: 시장(BTC) 데이터 (index는 날짜, 'close' 컬럼 필수)
        asset_data: 자산(ETH 등) 데이터 (index는 날짜, 'close' 컬럼 필수)
        lookback_days: 분석 기간 (기본 30일)

    Returns:
        베타 값 (float)

    Raises:
        ValueError: 데이터 부족 또는 형식 오류 시
    """
    # 1. 입력 데이터 검증
    if market_data.empty or asset_data.empty:
        raise ValueError('데이터 부족: 빈 DataFrame')

    if 'close' not in market_data.columns or 'close' not in asset_data.columns:
        raise ValueError('데이터 형식 오류: close 컬럼 없음')

    # 2. 날짜 기준으로 데이터 병합 (Inner Join)
    market_df = market_data.reset_index()[['index', 'close']].copy()
    market_df.columns = ['date', 'market_close']

    asset_df = asset_data.reset_index()[['index', 'close']].copy()
    asset_df.columns = ['date', 'asset_close']

    merged = pd.merge(market_df, asset_df, on='date', how='inner')

    if len(merged) < lookback_days:
        raise ValueError(
            f'데이터 부족 (병합 후 {len(merged)}일 < {lookback_days}일)'
        )

    # 3. 수익률 계산
    merged['market_return'] = merged['market_close'].pct_change()
    merged['asset_return'] = merged['asset_close'].pct_change()

    # NaN 제거
    merged = merged.dropna()

    if len(merged) < lookback_days:
        raise ValueError(
            f'데이터 부족 (NaN 제거 후 {len(merged)}일)'
        )

    # 4. 최근 N일 데이터 추출
    recent = merged.tail(lookback_days)

    market_returns = recent['market_return'].values
    asset_returns = recent['asset_return'].values

    # 5. 베타 계산 (CAPM: β = Cov(Asset, Market) / Var(Market))
    covariance = np.cov(market_returns, asset_returns)[0][1]
    market_variance = np.var(market_returns)

    if market_variance == 0 or np.isclose(market_variance, 0):
        # 시장 가격 변동이 없는 경우
        return 1.0

    beta = covariance / market_variance

    return float(beta)


def calculate_alpha(
    market_data: pd.DataFrame,
    asset_data: pd.DataFrame,
    lookback_days: int = 30
) -> float:
    """
    알파 계산 (초과 수익률).

    알파(Alpha): 자산의 시장 대비 초과 수익률
    - 알파 < 0: 자산이 시장 대비 수익률이 낮음
    - 알파 > 0: 자산이 시장 대비 수익률이 높음

    Args:
        market_data: 시장(BTC) 데이터
        asset_data: 자산(ETH 등) 데이터
        lookback_days: 분석 기간

    Returns:
        알파 값 (%)

    Raises:
        ValueError: 데이터 부족 또는 형식 오류 시
    """
    # 베타 계산
    beta = calculate_market_beta(market_data, asset_data, lookback_days)

    # 데이터 병합
    market_df = market_data.reset_index()[['index', 'close']].copy()
    market_df.columns = ['date', 'market_close']

    asset_df = asset_data.reset_index()[['index', 'close']].copy()
    asset_df.columns = ['date', 'asset_close']

    merged = pd.merge(market_df, asset_df, on='date', how='inner')

    # 수익률 계산
    merged['market_return'] = merged['market_close'].pct_change()
    merged['asset_return'] = merged['asset_close'].pct_change()
    merged = merged.dropna()

    recent = merged.tail(lookback_days)

    if len(recent) == 0:
        return 0.0

    # 알파 계산 (최근 1일 기준: α = Asset_return - β * Market_return)
    market_returns = recent['market_return'].values
    asset_returns = recent['asset_return'].values

    if len(market_returns) > 0 and len(asset_returns) > 0:
        expected_return = beta * market_returns[-1]
        actual_return = asset_returns[-1]
        alpha = actual_return - expected_return
    else:
        alpha = 0.0

    # 백분율로 변환
    return float(alpha * 100)


def calculate_correlation(
    market_data: pd.DataFrame,
    asset_data: pd.DataFrame,
    lookback_days: int = 30
) -> float:
    """
    시장-자산 상관계수 계산.

    상관계수: -1 (완전 반대) ~ +1 (완전 동행)

    Args:
        market_data: 시장(BTC) 데이터
        asset_data: 자산(ETH 등) 데이터
        lookback_days: 분석 기간

    Returns:
        상관계수 (float, -1 ~ 1)

    Raises:
        ValueError: 데이터 부족 또는 형식 오류 시
    """
    # 데이터 병합
    market_df = market_data.reset_index()[['index', 'close']].copy()
    market_df.columns = ['date', 'market_close']

    asset_df = asset_data.reset_index()[['index', 'close']].copy()
    asset_df.columns = ['date', 'asset_close']

    merged = pd.merge(market_df, asset_df, on='date', how='inner')

    if len(merged) < lookback_days:
        raise ValueError(
            f'데이터 부족 (병합 후 {len(merged)}일 < {lookback_days}일)'
        )

    # 수익률 계산
    merged['market_return'] = merged['market_close'].pct_change()
    merged['asset_return'] = merged['asset_close'].pct_change()
    merged = merged.dropna()

    recent = merged.tail(lookback_days)

    # 상관계수 계산
    correlation = recent['market_return'].corr(recent['asset_return'])

    return float(correlation)


def assess_market_risk(
    btc_return_1d: float,
    correlation: float
) -> str:
    """
    시장 리스크 판단.

    BTC 급락 시 높은 상관계수를 가진 자산은 high risk로 판단합니다.

    Args:
        btc_return_1d: BTC 1일 수익률 (%)
        correlation: 시장-자산 상관계수 (-1 ~ 1)

    Returns:
        리스크 레벨: "high", "medium", "low"
    """
    # BTC 급락 (-5% 이상) + 높은 상관계수 (0.7+) = HIGH RISK
    if btc_return_1d < -5.0 and correlation > 0.7:
        return "high"

    # BTC 급락 (-3% ~ -5%) + 중간 상관계수 (0.5+) = MEDIUM RISK
    if btc_return_1d < -3.0 and correlation > 0.5:
        return "medium"

    # 그 외 = LOW RISK
    return "low"
