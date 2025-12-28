"""
시장 상관관계 분석 모듈 (BTC-ETH 베타/알파 계산)
"""
import pandas as pd
import numpy as np
from typing import Dict, Any
from ..utils.logger import Logger


def calculate_market_risk(
    btc_data: pd.DataFrame,
    eth_data: pd.DataFrame,
    lookback_days: int = 30
) -> Dict[str, Any]:
    """
    시장 베타 및 알파 계산 (CAPM 모델 기반)
    
    베타(Beta):
    - ETH가 BTC 대비 얼마나 민감하게 반응하는지 측정
    - 베타 > 1.2: ETH가 BTC보다 1.2배 민감 (BTC 하락 시 ETH 더 크게 하락)
    - 베타 < 0.8: ETH가 BTC보다 덜 민감
    
    알파(Alpha):
    - ETH의 BTC 대비 초과 수익률
    - 알파 < 0: ETH가 BTC 대비 수익률이 낮음
    - 알파 > 0: ETH가 BTC 대비 수익률이 높음
    
    ⚠️ 중요: 날짜 기준으로 데이터를 병합해야 정확한 상관관계 계산 가능
    
    Args:
        btc_data: BTC 차트 데이터 (index는 날짜, 'close' 컬럼 필수)
        eth_data: ETH 차트 데이터 (index는 날짜, 'close' 컬럼 필수)
        lookback_days: 분석 기간 (기본 30일)
        
    Returns:
        {
            'market_risk': 'high' | 'medium' | 'low' | 'unknown',
            'risk_reason': str,  # 위험 판단 근거
            'beta': float,  # ETH 베타 (BTC 대비 민감도)
            'alpha': float,  # ETH 알파 (초과 수익률)
            'btc_return_1d': float,  # BTC 1일 수익률
            'correlation': float  # BTC-ETH 상관계수
        }
    """
    try:
        # 1. 입력 데이터 검증
        if btc_data.empty or eth_data.empty:
            return _create_unknown_result('빈 데이터프레임')
        
        if 'close' not in btc_data.columns or 'close' not in eth_data.columns:
            return _create_unknown_result('close 컬럼 없음')
        
        # 2. 날짜 기준으로 데이터 병합 (Inner Join)
        btc_df = btc_data.reset_index()[['index', 'close']].copy()
        btc_df.columns = ['date', 'btc_close']
        
        eth_df = eth_data.reset_index()[['index', 'close']].copy()
        eth_df.columns = ['date', 'eth_close']
        
        # 날짜 기준 병합 (겹치는 날짜만 사용)
        merged = pd.merge(btc_df, eth_df, on='date', how='inner')
        
        if len(merged) < lookback_days:
            return _create_unknown_result(
                f'데이터 부족 (병합 후 {len(merged)}일 < {lookback_days}일)'
            )
        
        # 3. 수익률 계산 (병합된 데이터 기준)
        merged['btc_return'] = merged['btc_close'].pct_change()
        merged['eth_return'] = merged['eth_close'].pct_change()
        
        # NaN 제거
        merged = merged.dropna()
        
        if len(merged) < lookback_days:
            return _create_unknown_result(
                f'유효 데이터 부족 (NaN 제거 후 {len(merged)}일)'
            )
        
        # 4. 최근 N일 데이터 추출
        recent = merged.tail(lookback_days)
        
        btc_returns = recent['btc_return'].values
        eth_returns = recent['eth_return'].values
        
        # 5. 베타 계산 (CAPM: β = Cov(ETH, BTC) / Var(BTC))
        covariance = np.cov(btc_returns, eth_returns)[0][1]
        btc_variance = np.var(btc_returns)
        
        if btc_variance == 0 or np.isclose(btc_variance, 0):
            # BTC 가격 변동이 없는 경우
            beta = 1.0
        else:
            beta = covariance / btc_variance
        
        # 6. 알파 계산 (최근 1일 기준: α = ETH_return - β * BTC_return)
        if len(btc_returns) > 0 and len(eth_returns) > 0:
            expected_return = beta * btc_returns[-1]
            actual_return = eth_returns[-1]
            alpha = actual_return - expected_return
            btc_return_1d = btc_returns[-1]
        else:
            alpha = 0.0
            btc_return_1d = 0.0
        
        # 7. 상관계수 계산
        correlation = float(np.corrcoef(btc_returns, eth_returns)[0][1])
        
        # 8. 위험 판단
        btc_dropping = btc_return_1d < -0.01  # BTC 1% 이상 하락
        
        if btc_dropping and beta > 1.2 and alpha < 0:
            # 고위험: BTC 하락 중 + ETH 민감도 높음 + 초과 수익 없음
            return {
                'market_risk': 'high',
                'risk_reason': f'BTC 하락 중({btc_return_1d*100:.2f}%), ETH 베타={beta:.2f}, 알파={alpha:.2%}',
                'beta': float(beta),
                'alpha': float(alpha),
                'btc_return_1d': float(btc_return_1d),
                'correlation': correlation
            }
        elif btc_dropping and beta > 0.8:
            # 중위험: BTC 하락 중 + ETH 민감도 보통 이상
            return {
                'market_risk': 'medium',
                'risk_reason': f'BTC 하락 중({btc_return_1d*100:.2f}%), ETH 베타={beta:.2f}',
                'beta': float(beta),
                'alpha': float(alpha),
                'btc_return_1d': float(btc_return_1d),
                'correlation': correlation
            }
        
        # 저위험: 정상 시장
        return {
            'market_risk': 'low',
            'risk_reason': '시장 리스크 낮음',
            'beta': float(beta),
            'alpha': float(alpha),
            'btc_return_1d': float(btc_return_1d),
            'correlation': correlation
        }
        
    except Exception as e:
        Logger.print_error(f"시장 리스크 계산 실패: {e}")
        return _create_unknown_result(f'계산 오류: {str(e)}')


def _create_unknown_result(reason: str) -> Dict[str, Any]:
    """
    알 수 없는 상태 결과 생성
    
    Args:
        reason: 알 수 없는 이유
        
    Returns:
        기본값으로 채워진 결과 딕셔너리
    """
    return {
        'market_risk': 'unknown',
        'risk_reason': reason,
        'beta': 1.0,
        'alpha': 0.0,
        'btc_return_1d': 0.0,
        'correlation': 0.0
    }



