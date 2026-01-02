"""
포트폴리오 매니저 (Portfolio Manager)

다중 코인 포지션을 관리하는 포트폴리오 레벨 매니저입니다.

역할:
- 최대 3개 코인 동시 보유 관리
- 자본 배분 (코인당 최대 40%)
- 포트폴리오 레벨 리스크 관리
- 진입 가능 여부 판단
- 전체 손익 추적

설계 원칙:
- 개별 포지션 관리는 PositionAnalyzer에 위임
- 포트폴리오 레벨의 의사결정만 담당
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..api.interfaces import IExchangeClient
from ..utils.logger import Logger
from .service import PositionService


class TradingMode(Enum):
    """거래 모드"""
    ENTRY = "entry"           # 진입 모드 (포지션 없음 또는 추가 가능)
    MANAGEMENT = "management"  # 관리 모드 (포지션 있음)
    BLOCKED = "blocked"        # 차단 (서킷 브레이커 등)


@dataclass
class PortfolioPosition:
    """포트폴리오 내 개별 포지션"""
    ticker: str
    symbol: str  # 코인 심볼 (ETH, BTC 등)
    amount: float
    avg_buy_price: float
    current_price: float
    entry_time: Optional[datetime] = None

    @property
    def current_value(self) -> float:
        """현재 평가금액"""
        return self.amount * self.current_price

    @property
    def total_cost(self) -> float:
        """총 매수금액"""
        return self.amount * self.avg_buy_price

    @property
    def profit_loss(self) -> float:
        """손익 금액"""
        return self.current_value - self.total_cost

    @property
    def profit_rate(self) -> float:
        """수익률 (%)"""
        if self.total_cost <= 0:
            return 0.0
        return (self.profit_loss / self.total_cost) * 100

    @property
    def holding_hours(self) -> float:
        """보유 시간 (시간)"""
        if self.entry_time is None:
            return 0.0
        delta = datetime.now() - self.entry_time
        return delta.total_seconds() / 3600


@dataclass
class PortfolioStatus:
    """포트폴리오 전체 상태"""
    positions: List[PortfolioPosition]
    krw_balance: float
    total_invested: float
    total_current_value: float
    total_profit_loss: float
    total_profit_rate: float
    position_count: int
    trading_mode: TradingMode
    can_open_new_position: bool
    available_capital: float
    capital_per_position: float


class PortfolioManager:
    """
    포트폴리오 매니저

    다중 코인 포지션을 포트폴리오 레벨에서 관리합니다.
    """

    # 포트폴리오 설정
    MAX_POSITIONS = 3  # 최대 동시 보유 코인 수
    MAX_ALLOCATION_PER_COIN = 0.4  # 코인당 최대 자본 비율 (40%)
    MIN_POSITION_VALUE = 10000  # 최소 포지션 가치 (1만원)
    RESERVE_RATIO = 0.1  # 예비 자금 비율 (10%)

    # 포트폴리오 레벨 리스크
    PORTFOLIO_DAILY_LOSS_LIMIT = -0.10  # 일일 손실 한도 (-10%)
    PORTFOLIO_WEEKLY_LOSS_LIMIT = -0.15  # 주간 손실 한도 (-15%)

    def __init__(
        self,
        exchange_client: IExchangeClient,
        max_positions: int = MAX_POSITIONS,
        max_allocation_per_coin: float = MAX_ALLOCATION_PER_COIN
    ):
        """
        Args:
            exchange_client: 거래소 클라이언트
            max_positions: 최대 동시 포지션 수
            max_allocation_per_coin: 코인당 최대 자본 비율
        """
        self.exchange = exchange_client
        self.position_service = PositionService(exchange_client)
        self.max_positions = max_positions
        self.max_allocation_per_coin = max_allocation_per_coin

        # 일일/주간 손익 추적 (메모리 기반, 실제로는 DB 사용 권장)
        self._daily_pnl = 0.0
        self._weekly_pnl = 0.0
        self._last_reset_date = datetime.now().date()

    def get_portfolio_status(self, tickers: Optional[List[str]] = None) -> PortfolioStatus:
        """
        포트폴리오 전체 상태 조회

        Args:
            tickers: 조회할 코인 리스트 (None이면 전체 잔고에서 탐색)

        Returns:
            PortfolioStatus: 포트폴리오 상태
        """
        # KRW 잔고 조회
        krw_balance = self.exchange.get_balance("KRW")
        if krw_balance is None:
            krw_balance = 0.0

        # 전체 잔고 조회
        balances = self.exchange.get_balances()
        if not balances:
            balances = []

        # 포지션 목록 구성
        positions: List[PortfolioPosition] = []
        total_invested = 0.0
        total_current_value = 0.0

        for balance in balances:
            currency = balance.get('currency', '')
            if currency == 'KRW':
                continue

            amount = float(balance.get('balance', 0)) + float(balance.get('locked', 0))
            avg_buy_price = float(balance.get('avg_buy_price', 0))

            # 최소 포지션 가치 체크
            if amount <= 0 or avg_buy_price <= 0:
                continue

            ticker = f"KRW-{currency}"

            # 특정 티커만 조회하는 경우
            if tickers and ticker not in tickers:
                continue

            current_price = self.exchange.get_current_price(ticker)
            if current_price is None or current_price <= 0:
                continue

            position_value = amount * current_price
            if position_value < self.MIN_POSITION_VALUE:
                continue

            position = PortfolioPosition(
                ticker=ticker,
                symbol=currency,
                amount=amount,
                avg_buy_price=avg_buy_price,
                current_price=current_price
            )

            positions.append(position)
            total_invested += position.total_cost
            total_current_value += position.current_value

        # 전체 손익 계산
        total_profit_loss = total_current_value - total_invested
        total_profit_rate = (total_profit_loss / total_invested * 100) if total_invested > 0 else 0.0

        # 거래 모드 결정
        trading_mode = self._determine_trading_mode(positions, total_profit_rate)

        # 신규 진입 가능 여부
        can_open = self._can_open_new_position(positions, krw_balance, trading_mode)

        # 가용 자본 계산
        total_capital = krw_balance + total_current_value
        available_capital = self._calculate_available_capital(
            krw_balance, total_capital, len(positions)
        )

        # 포지션당 자본
        remaining_slots = self.max_positions - len(positions)
        capital_per_position = available_capital / remaining_slots if remaining_slots > 0 else 0

        return PortfolioStatus(
            positions=positions,
            krw_balance=krw_balance,
            total_invested=total_invested,
            total_current_value=total_current_value,
            total_profit_loss=total_profit_loss,
            total_profit_rate=total_profit_rate,
            position_count=len(positions),
            trading_mode=trading_mode,
            can_open_new_position=can_open,
            available_capital=available_capital,
            capital_per_position=capital_per_position
        )

    def _determine_trading_mode(
        self,
        positions: List[PortfolioPosition],
        total_profit_rate: float
    ) -> TradingMode:
        """
        거래 모드 결정

        Returns:
            TradingMode: 현재 거래 모드
        """
        # 서킷 브레이커 체크
        if self._daily_pnl <= self.PORTFOLIO_DAILY_LOSS_LIMIT:
            return TradingMode.BLOCKED

        if self._weekly_pnl <= self.PORTFOLIO_WEEKLY_LOSS_LIMIT:
            return TradingMode.BLOCKED

        # 포지션 유무에 따른 모드
        if len(positions) == 0:
            return TradingMode.ENTRY
        elif len(positions) < self.max_positions:
            return TradingMode.ENTRY  # 추가 진입 가능
        else:
            return TradingMode.MANAGEMENT  # 관리만

    def _can_open_new_position(
        self,
        positions: List[PortfolioPosition],
        krw_balance: float,
        trading_mode: TradingMode
    ) -> bool:
        """신규 포지션 진입 가능 여부"""
        # 차단 상태
        if trading_mode == TradingMode.BLOCKED:
            return False

        # 최대 포지션 수 체크
        if len(positions) >= self.max_positions:
            return False

        # 최소 자본 체크
        if krw_balance < self.MIN_POSITION_VALUE:
            return False

        return True

    def _calculate_available_capital(
        self,
        krw_balance: float,
        total_capital: float,
        current_positions: int
    ) -> float:
        """
        가용 자본 계산

        Args:
            krw_balance: 현금 잔고
            total_capital: 총 자본 (현금 + 투자금)
            current_positions: 현재 포지션 수

        Returns:
            신규 진입에 사용 가능한 자본
        """
        # 예비 자금 제외
        reserve = total_capital * self.RESERVE_RATIO
        available = krw_balance - reserve

        # 코인당 최대 배분 적용
        max_per_coin = total_capital * self.max_allocation_per_coin
        available = min(available, max_per_coin)

        return max(0, available)

    def get_position(self, ticker: str) -> Optional[PortfolioPosition]:
        """특정 코인의 포지션 조회"""
        status = self.get_portfolio_status([ticker])
        for pos in status.positions:
            if pos.ticker == ticker:
                return pos
        return None

    def has_position(self, ticker: str) -> bool:
        """특정 코인 포지션 보유 여부"""
        position = self.get_position(ticker)
        return position is not None

    def get_position_tickers(self) -> List[str]:
        """보유 중인 코인 티커 리스트"""
        status = self.get_portfolio_status()
        return [pos.ticker for pos in status.positions]

    def get_entry_capital(self, ticker: str) -> float:
        """
        특정 코인 진입 시 사용할 자본 계산

        Args:
            ticker: 진입할 코인

        Returns:
            진입에 사용할 자본 (KRW)
        """
        status = self.get_portfolio_status()

        if not status.can_open_new_position:
            return 0.0

        return status.capital_per_position

    def record_trade_result(self, ticker: str, pnl: float, pnl_pct: float) -> None:
        """
        거래 결과 기록 (손익 추적)

        Args:
            ticker: 거래 코인
            pnl: 손익 금액
            pnl_pct: 손익률 (%)
        """
        # 일일 손익 누적
        self._daily_pnl += pnl_pct / 100

        # 주간 손익 누적
        self._weekly_pnl += pnl_pct / 100

        Logger.print_info(f"📊 포트폴리오 손익 업데이트: {ticker}")
        Logger.print_info(f"  일일 누적: {self._daily_pnl*100:+.2f}%")
        Logger.print_info(f"  주간 누적: {self._weekly_pnl*100:+.2f}%")

        # 날짜 변경 체크 (일일 리셋)
        today = datetime.now().date()
        if today != self._last_reset_date:
            self._daily_pnl = pnl_pct / 100
            self._last_reset_date = today

    def check_portfolio_risk(self) -> Dict[str, Any]:
        """
        포트폴리오 레벨 리스크 체크

        Returns:
            리스크 체크 결과
        """
        daily_limit_hit = self._daily_pnl <= self.PORTFOLIO_DAILY_LOSS_LIMIT
        weekly_limit_hit = self._weekly_pnl <= self.PORTFOLIO_WEEKLY_LOSS_LIMIT

        return {
            'allowed': not (daily_limit_hit or weekly_limit_hit),
            'daily_pnl': self._daily_pnl,
            'weekly_pnl': self._weekly_pnl,
            'daily_limit': self.PORTFOLIO_DAILY_LOSS_LIMIT,
            'weekly_limit': self.PORTFOLIO_WEEKLY_LOSS_LIMIT,
            'daily_limit_hit': daily_limit_hit,
            'weekly_limit_hit': weekly_limit_hit,
            'reason': self._get_risk_reason(daily_limit_hit, weekly_limit_hit)
        }

    def _get_risk_reason(self, daily_hit: bool, weekly_hit: bool) -> str:
        """리스크 발동 이유"""
        if daily_hit:
            return f"일일 손실 한도 도달 ({self._daily_pnl*100:.2f}% ≤ {self.PORTFOLIO_DAILY_LOSS_LIMIT*100:.2f}%)"
        if weekly_hit:
            return f"주간 손실 한도 도달 ({self._weekly_pnl*100:.2f}% ≤ {self.PORTFOLIO_WEEKLY_LOSS_LIMIT*100:.2f}%)"
        return ""

    def print_portfolio_summary(self) -> None:
        """포트폴리오 요약 출력"""
        status = self.get_portfolio_status()

        Logger.print_header("📊 포트폴리오 현황")
        print(f"  거래 모드: {status.trading_mode.value}")
        print(f"  보유 포지션: {status.position_count}/{self.max_positions}개")
        print(f"  신규 진입 가능: {'Yes' if status.can_open_new_position else 'No'}")
        print()
        print(f"  현금 잔고: {status.krw_balance:,.0f} KRW")
        print(f"  투자 금액: {status.total_invested:,.0f} KRW")
        print(f"  평가 금액: {status.total_current_value:,.0f} KRW")
        print(f"  총 손익: {status.total_profit_loss:+,.0f} KRW ({status.total_profit_rate:+.2f}%)")
        print()

        if status.positions:
            print("  [보유 포지션]")
            for pos in status.positions:
                print(f"    {pos.symbol}: {pos.current_value:,.0f} KRW ({pos.profit_rate:+.2f}%)")

        if status.can_open_new_position:
            print()
            print(f"  [신규 진입 가용 자본]")
            print(f"    가용 자본: {status.available_capital:,.0f} KRW")
            print(f"    포지션당: {status.capital_per_position:,.0f} KRW")

        print(Logger._separator())
