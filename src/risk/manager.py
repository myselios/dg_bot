"""
리스크 관리 모듈

실전 투자에서 필수적인 리스크 관리 기능을 제공합니다.
- 손절/익절 자동 체크
- Circuit Breaker (일일 손실 한도)
- 포지션 사이징 (Kelly Criterion)
- 거래 빈도 제한
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from ..utils.logger import Logger
from .state_manager import RiskStateManager


@dataclass
class RiskLimits:
    """리스크 한도 설정"""
    # 손절/익절 (고정 비율 방식)
    stop_loss_pct: float = -5.0  # 손절: -5%
    take_profit_pct: float = 10.0  # 익절: +10%

    # 손절/익절 (ATR 기반 방식)
    use_atr_based_stops: bool = False  # ATR 기반 손절/익절 사용 여부
    stop_loss_atr_multiplier: float = 1.5  # 손절: 진입가 - ATR × 1.5
    take_profit_atr_multiplier: float = 2.5  # 익절: 진입가 + ATR × 2.5

    # Circuit Breaker
    daily_loss_limit_pct: float = -10.0  # 일일 최대 손실: -10%
    weekly_loss_limit_pct: float = -15.0  # 주간 최대 손실: -15%

    # 거래 빈도
    min_trade_interval_hours: int = 4  # 최소 거래 간격: 4시간
    max_daily_trades: int = 5  # 일일 최대 거래 횟수

    # 포지션 사이징
    max_position_size_pct: float = 30.0  # 최대 포지션 크기: 30%
    min_position_size_pct: float = 5.0  # 최소 포지션 크기: 5%

    # 트레일링 스탑
    use_trailing_stop: bool = False  # 트레일링 스탑 사용 여부
    trailing_stop_atr_multiplier: float = 2.0  # 트레일링 스탑: 최고가 - ATR × 2

    # 분할 익절
    use_partial_profit: bool = False  # 분할 익절 사용 여부
    take_profit_level_1_pct: float = 5.0  # 1차 익절: +5%
    take_profit_level_2_pct: float = 10.0  # 2차 익절: +10%
    partial_sell_ratio: float = 0.5  # 1차 익절 시 50% 매도


class RiskManager:
    """리스크 관리자 - 실전 투자의 핵심"""

    def __init__(self, limits: Optional[RiskLimits] = None, persist_state: bool = True):
        """
        리스크 관리자 초기화

        Args:
            limits: 리스크 한도 설정
            persist_state: 상태 영속성 사용 여부 (True: JSON 파일로 저장/로드)
        """
        self.limits = limits or RiskLimits()
        self.persist_state = persist_state

        # 상태 로드
        if persist_state:
            state = RiskStateManager.load_state()
            self.daily_pnl = state.get('daily_pnl', 0.0)
            self.daily_trade_count = state.get('daily_trade_count', 0)
            self.safe_mode = state.get('safe_mode', False)
            self.safe_mode_reason = state.get('safe_mode_reason', '')

            # last_trade_time 파싱
            last_trade_str = state.get('last_trade_time')
            if last_trade_str:
                try:
                    self.last_trade_time = datetime.fromisoformat(last_trade_str)
                except (ValueError, TypeError):
                    self.last_trade_time = None
            else:
                self.last_trade_time = None

            # weekly_pnl 계산 (최근 7일간 합계)
            self.weekly_pnl = RiskStateManager.calculate_weekly_pnl()
        else:
            # 영속성 사용 안 함 (테스트용)
            self.last_trade_time: Optional[datetime] = None
            self.daily_trade_count: int = 0
            self.daily_pnl: float = 0.0
            self.weekly_pnl: float = 0.0
            self.safe_mode: bool = False
            self.safe_mode_reason: str = ""

        # 트레일링 스탑 상태
        self.trailing_stop_price: Optional[float] = None
        self.highest_price_since_entry: Optional[float] = None

    def check_position_limits(
        self,
        position: Optional[Dict[str, Any]],
        current_price: float
    ) -> Dict[str, Any]:
        """
        포지션 손익 체크 - 손절/익절 발동

        Returns:
            {
                'action': 'hold' | 'stop_loss' | 'take_profit',
                'reason': str,
                'pnl_pct': float
            }
        """
        if not position or current_price <= 0:
            return {'action': 'hold', 'reason': '포지션 없음', 'pnl_pct': 0.0}

        avg_buy_price = position.get('avg_buy_price', 0)
        if avg_buy_price <= 0:
            return {'action': 'hold', 'reason': '매수가 정보 없음', 'pnl_pct': 0.0}

        # 손익률 계산
        pnl_pct = ((current_price - avg_buy_price) / avg_buy_price) * 100

        # 손절 체크
        if pnl_pct <= self.limits.stop_loss_pct:
            Logger.print_error(f"🚨 손절 발동: {pnl_pct:.2f}% <= {self.limits.stop_loss_pct}%")
            return {
                'action': 'stop_loss',
                'reason': f'손절 발동 (손실: {pnl_pct:.2f}%)',
                'pnl_pct': pnl_pct
            }

        # 익절 체크
        if pnl_pct >= self.limits.take_profit_pct:
            Logger.print_success(f"💰 익절 발동: {pnl_pct:.2f}% >= {self.limits.take_profit_pct}%")
            return {
                'action': 'take_profit',
                'reason': f'익절 발동 (수익: {pnl_pct:.2f}%)',
                'pnl_pct': pnl_pct
            }

        return {'action': 'hold', 'reason': '포지션 유지', 'pnl_pct': pnl_pct}

    def check_circuit_breaker(self) -> Dict[str, Any]:
        """
        Circuit Breaker 체크 - 일일/주간 손실 한도 초과 시 거래 중단

        Returns:
            {
                'allowed': bool,
                'reason': str,
                'daily_pnl': float,
                'weekly_pnl': float
            }
        """
        # 일일 손실 한도 체크
        if self.daily_pnl <= self.limits.daily_loss_limit_pct:
            self.enable_safe_mode(f"일일 손실 한도 초과: {self.daily_pnl:.2f}%")
            return {
                'allowed': False,
                'reason': f'일일 손실 한도 초과 ({self.daily_pnl:.2f}% <= {self.limits.daily_loss_limit_pct}%)',
                'daily_pnl': self.daily_pnl,
                'weekly_pnl': self.weekly_pnl
            }

        # 주간 손실 한도 체크
        if self.weekly_pnl <= self.limits.weekly_loss_limit_pct:
            self.enable_safe_mode(f"주간 손실 한도 초과: {self.weekly_pnl:.2f}%")
            return {
                'allowed': False,
                'reason': f'주간 손실 한도 초과 ({self.weekly_pnl:.2f}% <= {self.limits.weekly_loss_limit_pct}%)',
                'daily_pnl': self.daily_pnl,
                'weekly_pnl': self.weekly_pnl
            }

        return {
            'allowed': True,
            'reason': '정상 거래 가능',
            'daily_pnl': self.daily_pnl,
            'weekly_pnl': self.weekly_pnl
        }

    def check_trade_frequency(self) -> Dict[str, Any]:
        """
        거래 빈도 제한 체크

        Returns:
            {
                'allowed': bool,
                'reason': str,
                'hours_since_last_trade': float
            }
        """
        if not self.last_trade_time:
            return {
                'allowed': True,
                'reason': '첫 거래',
                'hours_since_last_trade': 0
            }

        # 마지막 거래 이후 시간 계산
        time_since_last = datetime.now() - self.last_trade_time
        hours_since_last = time_since_last.total_seconds() / 3600

        # 최소 거래 간격 체크
        if hours_since_last < self.limits.min_trade_interval_hours:
            return {
                'allowed': False,
                'reason': f'최소 거래 간격 미달 ({hours_since_last:.1f}시간 < {self.limits.min_trade_interval_hours}시간)',
                'hours_since_last_trade': hours_since_last
            }

        # 일일 최대 거래 횟수 체크
        if self.daily_trade_count >= self.limits.max_daily_trades:
            return {
                'allowed': False,
                'reason': f'일일 최대 거래 횟수 초과 ({self.daily_trade_count} >= {self.limits.max_daily_trades})',
                'hours_since_last_trade': hours_since_last
            }

        return {
            'allowed': True,
            'reason': '거래 빈도 정상',
            'hours_since_last_trade': hours_since_last
        }

    def calculate_kelly_position_size(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        current_capital: float
    ) -> float:
        """
        Kelly Criterion 기반 최적 포지션 크기 계산

        Kelly % = W - [(1-W) / R]
        W = 승률, R = 평균 수익/평균 손실

        Args:
            win_rate: 승률 (0~1)
            avg_win: 평균 수익률 (%)
            avg_loss: 평균 손실률 (%)
            current_capital: 현재 자본금

        Returns:
            최적 포지션 크기 (금액)
        """
        if avg_loss == 0 or win_rate <= 0 or win_rate >= 1:
            # Fallback: 기본 10%
            return current_capital * 0.1

        # Kelly 공식
        r = abs(avg_win / avg_loss)  # Risk-Reward Ratio
        kelly_pct = win_rate - ((1 - win_rate) / r)

        # 안전장치: Kelly의 절반 사용 (Half Kelly)
        kelly_pct = kelly_pct * 0.5

        # 범위 제한
        kelly_pct = max(self.limits.min_position_size_pct / 100, kelly_pct)
        kelly_pct = min(self.limits.max_position_size_pct / 100, kelly_pct)

        return current_capital * kelly_pct

    def enable_safe_mode(self, reason: str):
        """안전 모드 활성화"""
        self.safe_mode = True
        self.safe_mode_reason = reason
        Logger.print_error(f"⛔ 안전 모드 활성화: {reason}")

        # 상태 저장
        if self.persist_state:
            self._save_state()

    def disable_safe_mode(self):
        """안전 모드 해제"""
        self.safe_mode = False
        self.safe_mode_reason = ""
        Logger.print_success("✅ 안전 모드 해제")

    def record_trade(self, pnl_pct: float):
        """거래 기록 및 손익 업데이트"""
        self.last_trade_time = datetime.now()
        self.daily_trade_count += 1
        self.daily_pnl += pnl_pct
        self.weekly_pnl += pnl_pct

        Logger.print_info(f"📝 거래 기록: 손익 {pnl_pct:+.2f}% | 일일 누적: {self.daily_pnl:+.2f}%")

        # 상태 저장
        if self.persist_state:
            self._save_state()

    def reset_daily_stats(self):
        """일일 통계 초기화 (매일 자정 실행)"""
        self.daily_trade_count = 0
        self.daily_pnl = 0.0
        Logger.print_info("🔄 일일 통계 초기화")

    def reset_weekly_stats(self):
        """주간 통계 초기화 (매주 월요일 실행)"""
        self.weekly_pnl = 0.0
        Logger.print_info("🔄 주간 통계 초기화")

        # 상태 저장
        if self.persist_state:
            RiskStateManager.reset_weekly_state()

    def _save_state(self):
        """현재 상태를 JSON 파일에 저장"""
        state = {
            'daily_pnl': self.daily_pnl,
            'daily_trade_count': self.daily_trade_count,
            'last_trade_time': self.last_trade_time.isoformat() if self.last_trade_time else None,
            'weekly_pnl': self.weekly_pnl,
            'safe_mode': self.safe_mode,
            'safe_mode_reason': self.safe_mode_reason
        }
        RiskStateManager.save_state(state)

    def calculate_stop_loss_price(
        self,
        entry_price: float,
        atr: Optional[float] = None
    ) -> float:
        """
        ATR 기반 손절가 계산

        Args:
            entry_price: 진입가
            atr: ATR 값 (None이면 고정 비율 사용)

        Returns:
            손절가
        """
        if self.limits.use_atr_based_stops and atr is not None:
            # ATR 기반 손절가
            return entry_price - (atr * self.limits.stop_loss_atr_multiplier)
        else:
            # 고정 비율 기반 손절가
            return entry_price * (1 + self.limits.stop_loss_pct / 100)

    def calculate_take_profit_price(
        self,
        entry_price: float,
        atr: Optional[float] = None
    ) -> float:
        """
        ATR 기반 익절가 계산

        Args:
            entry_price: 진입가
            atr: ATR 값 (None이면 고정 비율 사용)

        Returns:
            익절가
        """
        if self.limits.use_atr_based_stops and atr is not None:
            # ATR 기반 익절가
            return entry_price + (atr * self.limits.take_profit_atr_multiplier)
        else:
            # 고정 비율 기반 익절가
            return entry_price * (1 + self.limits.take_profit_pct / 100)

    def update_trailing_stop(
        self,
        position: Optional[Dict],
        current_price: float,
        atr: float
    ) -> Optional[float]:
        """
        트레일링 스탑 업데이트

        트레일링 스탑 = max(기존 손절가, 최고가 - ATR × 2)

        Args:
            position: 현재 포지션
            current_price: 현재가
            atr: ATR 값

        Returns:
            업데이트된 트레일링 스탑 가격 (또는 None)
        """
        if not self.limits.use_trailing_stop:
            return None

        if not position or current_price <= 0:
            return None

        avg_buy_price = position.get('avg_buy_price', 0)
        if avg_buy_price <= 0:
            return None

        # 최고가 업데이트
        if self.highest_price_since_entry is None:
            self.highest_price_since_entry = current_price
        else:
            self.highest_price_since_entry = max(
                self.highest_price_since_entry,
                current_price
            )

        # 초기 손절가 계산 (ATR 기반)
        initial_stop = self.calculate_stop_loss_price(avg_buy_price, atr)

        # 트레일링 스탑 계산
        trailing_stop = self.highest_price_since_entry - (atr * self.limits.trailing_stop_atr_multiplier)

        # 최종 손절가 = max(초기 손절가, 트레일링 스탑)
        self.trailing_stop_price = max(initial_stop, trailing_stop)

        return self.trailing_stop_price

    def check_trailing_stop(
        self,
        position: Optional[Dict],
        current_price: float,
        atr: float
    ) -> Dict[str, Any]:
        """
        트레일링 스탑 체크

        Args:
            position: 현재 포지션
            current_price: 현재가
            atr: ATR 값

        Returns:
            {
                'action': 'hold' | 'trailing_stop',
                'reason': str,
                'pnl_pct': float
            }
        """
        if not self.limits.use_trailing_stop:
            return {'action': 'hold', 'reason': '트레일링 스탑 비활성화', 'pnl_pct': 0}

        trailing_stop = self.update_trailing_stop(position, current_price, atr)

        if trailing_stop and current_price <= trailing_stop:
            avg_buy_price = position.get('avg_buy_price', 0)
            pnl_pct = ((current_price - avg_buy_price) / avg_buy_price) * 100 if avg_buy_price > 0 else 0

            Logger.print_warning(
                f"🛑 트레일링 스탑 발동: {current_price:,.0f}원 <= {trailing_stop:,.0f}원"
            )

            return {
                'action': 'trailing_stop',
                'reason': f'트레일링 스탑 발동 (손익: {pnl_pct:.2f}%)',
                'pnl_pct': pnl_pct
            }

        return {'action': 'hold', 'reason': '트레일링 스탑 유지', 'pnl_pct': 0}

    def check_partial_take_profit(
        self,
        position: Optional[Dict],
        current_price: float
    ) -> Dict[str, Any]:
        """
        분할 익절 체크

        1차 익절 (+5%): 50% 매도
        2차 익절 (+10%): 나머지 50% 매도

        Args:
            position: 현재 포지션
            current_price: 현재가

        Returns:
            {
                'action': 'hold' | 'partial_take_profit_1' | 'partial_take_profit_2',
                'reason': str,
                'sell_ratio': float,
                'pnl_pct': float
            }
        """
        if not self.limits.use_partial_profit:
            return {'action': 'hold', 'reason': '분할 익절 비활성화'}

        if not position or current_price <= 0:
            return {'action': 'hold', 'reason': '포지션 없음'}

        avg_buy_price = position.get('avg_buy_price', 0)
        if avg_buy_price <= 0:
            return {'action': 'hold', 'reason': '매수가 정보 없음'}

        pnl_pct = ((current_price - avg_buy_price) / avg_buy_price) * 100

        # 2차 익절 체크 (+10%)
        if pnl_pct >= self.limits.take_profit_level_2_pct:
            Logger.print_success(
                f"💰 2차 익절 발동: {pnl_pct:.2f}% >= {self.limits.take_profit_level_2_pct}%"
            )
            return {
                'action': 'partial_take_profit_2',
                'reason': f'2차 익절 (수익: {pnl_pct:.2f}%)',
                'sell_ratio': 1.0,  # 100% 매도
                'pnl_pct': pnl_pct
            }

        # 1차 익절 체크 (+5%)
        if pnl_pct >= self.limits.take_profit_level_1_pct:
            Logger.print_success(
                f"💰 1차 익절 발동: {pnl_pct:.2f}% >= {self.limits.take_profit_level_1_pct}%"
            )
            return {
                'action': 'partial_take_profit_1',
                'reason': f'1차 익절 (수익: {pnl_pct:.2f}%)',
                'sell_ratio': self.limits.partial_sell_ratio,  # 50% 매도
                'pnl_pct': pnl_pct
            }

        return {'action': 'hold', 'reason': '익절 조건 미달', 'pnl_pct': pnl_pct}
