"""
Phase 2: 승률↔손익비 연동 필터 (Expectancy Filter)

기대값 음수 조합을 차단하는 수학적 필터

핵심 공식:
- cost_R = cost_pct / avg_loss_pct
- gross = (win_rate × R) - (1 - win_rate)
- net = gross - cost_R
- R_min = ((1 - win_rate) + cost_R + margin_R) / win_rate

단위 규칙 (P0-3):
- 내부 로직: 모든 비율은 0~1로 통일 (예: 33% → 0.33)
- 설정/표시: % 단위 사용, 로직 진입 시 /100 변환
"""
from typing import Tuple


# ============================================================
# 상수 정의 (P0-7)
# ============================================================

AVG_LOSS_PCT_FLOOR = 0.002  # 0.2% 최소 손실 (안전장치)
# NOTE: floor는 운영 중 적용률(몇 % 트레이드에 적용됐는지) 반드시 로그/메트릭으로 모니터링


# ============================================================
# 핵심 함수
# ============================================================

def apply_avg_loss_floor(avg_loss_pct: float) -> float:
    """
    avg_loss_pct에 바닥값 적용 (P0-7)

    극단적으로 낮은 avg_loss_pct (0에 가까운 값)는 cost_R 계산 시
    무한대로 발산하므로 최소값(floor)을 적용합니다.

    Args:
        avg_loss_pct: 평균 손실률 (0~1)

    Returns:
        floor 적용된 avg_loss_pct
    """
    return max(avg_loss_pct, AVG_LOSS_PCT_FLOOR)


def calculate_cost_R(cost_pct: float, avg_loss_pct: float) -> float:
    """
    비용을 R 단위로 환산 (P0-12: cost_pct는 항상 외부에서 주입)

    R(Risk) 단위란: 1회 거래당 평균 손실을 1R로 정의
    cost_R = 왕복 거래 비용이 몇 R인지 계산

    Args:
        cost_pct: 왕복 비용 (0~1) - 반드시 Config에서 파생하여 주입
        avg_loss_pct: 평균 손실률 (0~1), floor 적용됨

    Returns:
        비용 R 값

    Example:
        cost_pct=0.0012 (0.12%), avg_loss_pct=0.01 (1%)
        cost_R = 0.0012 / 0.01 = 0.12
    """
    avg_loss_pct = apply_avg_loss_floor(avg_loss_pct)
    return cost_pct / avg_loss_pct


def calculate_net_expectancy(
    win_rate: float,
    avg_win_loss_ratio: float,
    avg_loss_pct: float,
    cost_pct: float,  # ⚠️ P0-12: 기본값 없음 - 반드시 Config에서 주입
) -> float:
    """
    순 기대값 계산 (R 단위)

    공식:
    - gross = (win_rate × R) - (1 - win_rate)
    - net = gross - cost_R

    Args:
        win_rate: 승률 (0~1)
        avg_win_loss_ratio: 평균 손익비 (R)
        avg_loss_pct: 평균 손실률 (0~1), floor 적용됨
        cost_pct: 왕복 비용 (0~1) - 반드시 Config에서 파생하여 주입

    Returns:
        순 기대값 (R 단위)
        - 양수: 수익 기대
        - 음수: 손실 기대
        - 0: 손익분기

    Example:
        승률 33% (p=0.33), R=2.5, avg_loss_pct=1%, cost_pct=0.12%

        1. cost_R = 0.0012 / 0.01 = 0.12
        2. gross = 0.33 × 2.5 - 0.67 = 0.825 - 0.67 = 0.155
        3. net = 0.155 - 0.12 = 0.035  ✅ 양수 (margin 충족)
    """
    cost_R = calculate_cost_R(cost_pct, avg_loss_pct)
    gross = (win_rate * avg_win_loss_ratio) - (1 - win_rate)
    return gross - cost_R


def check_expectancy_filter(
    win_rate: float,
    avg_win_loss_ratio: float,
    avg_loss_pct: float,
    cost_pct: float,  # ⚠️ P0-12: 기본값 없음
    margin_R: float = 0.05
) -> Tuple[bool, float]:
    """
    R-multiple 기반 기대값 필터 (P0-6, P0-12)

    순 기대값이 margin_R 이상이면 통과

    Args:
        win_rate: 승률 (0~1)
        avg_win_loss_ratio: 평균 손익비 (R)
        avg_loss_pct: 평균 손실률 (0~1)
        cost_pct: 왕복 비용 (0~1) - 반드시 Config에서 파생하여 주입
        margin_R: 최소 요구 기대값 (기본: 0.05R = 5% margin)

    Returns:
        (통과 여부, 순 기대값)
    """
    net_expectancy_R = calculate_net_expectancy(
        win_rate, avg_win_loss_ratio, avg_loss_pct, cost_pct
    )
    return net_expectancy_R >= margin_R, net_expectancy_R


def get_min_win_loss_ratio(
    win_rate: float,
    avg_loss_pct: float,
    cost_pct: float,  # ⚠️ P0-12: 기본값 없음
    margin_R: float = 0.05
) -> float:
    """
    승률에 따른 최소 손익비 계산 (P0-6, P0-12)

    공식: R_min = ((1 - win_rate) + cost_R + margin_R) / win_rate

    Args:
        win_rate: 승률 (0~1)
        avg_loss_pct: 평균 손실률 (0~1)
        cost_pct: 왕복 비용 (0~1) - 반드시 Config에서 파생하여 주입
        margin_R: 최소 요구 기대값 마진 (기본: 0.05R)

    Returns:
        최소 필요 손익비 (R_min)

    Example:
        승률 33%, avg_loss_pct=1%, cost_pct=0.12%, margin_R=0.05

        1. cost_R = 0.0012 / 0.01 = 0.12
        2. R_min = (0.67 + 0.12 + 0.05) / 0.33 = 0.84 / 0.33 = 2.545
    """
    cost_R = calculate_cost_R(cost_pct, avg_loss_pct)
    return ((1 - win_rate) + cost_R + margin_R) / win_rate


# ============================================================
# R_min 참조 표 (P0-2 수정된 값)
# ============================================================
# | 승률 | cost_R=0.12 | cost_R=0.2 | 설명 |
# |------|-------------|------------|------|
# | 30%  | 2.9         | 3.17       | 초저승률 |
# | 33%  | 2.55        | 2.79       | 저승률 |
# | 40%  | 1.93        | 2.13       | 중저승률 |
# | 50%  | 1.34        | 1.50       | 중간 |
# | 60%  | 0.95        | 1.08       | 중고승률 |
