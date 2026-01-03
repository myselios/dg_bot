"""
리스크 상태 관리자

프로그램 재시작 후에도 리스크 관리 상태를 유지합니다.
- daily_pnl: 일일 손익률 누적
- daily_trade_count: 일일 거래 횟수
- last_trade_time: 마지막 거래 시간
- weekly_pnl: 주간 손익률 누적

지원 스토리지:
- PostgreSQL (RiskStateRepository 사용) - 권장
- JSON 파일 (DEPRECATED, 하위 호환용)
"""
import json
from pathlib import Path
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, Optional, TYPE_CHECKING
from ..utils.logger import Logger

if TYPE_CHECKING:
    from src.infrastructure.adapters.persistence.risk_state_repository import RiskStateRepository


class RiskStateManager:
    """
    리스크 상태 관리자

    PostgreSQL Repository 사용 권장 (set_repository로 설정)
    JSON 파일은 DEPRECATED이며 하위 호환용으로만 유지됩니다.
    """

    # DEPRECATED: JSON 파일 기반 저장 (하위 호환용)
    STATE_FILE = Path("data/risk_state.json")

    # Repository 인스턴스 (PostgreSQL 사용 시)
    _repository: Optional["RiskStateRepository"] = None

    @classmethod
    def set_repository(cls, repository: "RiskStateRepository") -> None:
        """
        Repository 설정

        Args:
            repository: RiskStateRepository 인스턴스
        """
        cls._repository = repository
        Logger.print_info("🗄️ RiskStateManager: PostgreSQL Repository 설정됨")

    @staticmethod
    def save_state(state: Dict) -> None:
        """
        상태 저장

        Args:
            state: 저장할 상태 딕셔너리
                {
                    'daily_pnl': float,
                    'daily_trade_count': int,
                    'last_trade_time': str (ISO format),
                    'weekly_pnl': float,
                    'safe_mode': bool,
                    'safe_mode_reason': str
                }
        """
        # 디렉토리 생성
        RiskStateManager.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

        # 기존 상태 로드
        existing_state = RiskStateManager.load_all_states()

        # 오늘 날짜 키로 저장
        today = datetime.now().date().isoformat()
        existing_state[today] = {
            **state,
            'updated_at': datetime.now().isoformat()
        }

        # 7일 이전 데이터 삭제 (주간 손실 계산용으로 최소 7일 유지)
        cutoff = (datetime.now() - timedelta(days=7)).date().isoformat()
        existing_state = {
            k: v for k, v in existing_state.items()
            if k >= cutoff
        }

        # 파일에 저장
        with open(RiskStateManager.STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(existing_state, f, indent=2, ensure_ascii=False, default=str)

        Logger.print_info(f"📝 리스크 상태 저장 완료: {today}")

    @staticmethod
    def load_state() -> Dict:
        """
        오늘 날짜 상태 로드

        Returns:
            오늘 날짜의 상태 딕셔너리 (없으면 기본값)
        """
        all_states = RiskStateManager.load_all_states()
        today = datetime.now().date().isoformat()

        if today in all_states:
            state = all_states[today]
            Logger.print_info(f"📂 리스크 상태 로드: {today}")
            return state

        # 오늘 날짜 상태가 없으면 기본값 반환
        default_state = {
            'daily_pnl': 0.0,
            'daily_trade_count': 0,
            'last_trade_time': None,
            'weekly_pnl': 0.0,
            'safe_mode': False,
            'safe_mode_reason': ''
        }

        Logger.print_info(f"📂 리스크 상태 없음, 기본값 사용: {today}")
        return default_state

    @staticmethod
    def load_all_states() -> Dict:
        """
        모든 상태 로드

        Returns:
            날짜별 상태 딕셔너리 {날짜: 상태}
        """
        if not RiskStateManager.STATE_FILE.exists():
            return {}

        try:
            with open(RiskStateManager.STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            Logger.print_error(f"❌ 리스크 상태 파일 로드 실패: {e}")
            return {}

    @staticmethod
    def reset_daily_state() -> None:
        """
        일일 상태 초기화 (자정 실행)

        daily_pnl과 daily_trade_count만 초기화하고,
        weekly_pnl은 유지합니다.
        """
        state = RiskStateManager.load_state()
        state['daily_pnl'] = 0.0
        state['daily_trade_count'] = 0
        state['safe_mode'] = False
        state['safe_mode_reason'] = ''

        RiskStateManager.save_state(state)
        Logger.print_info("🔄 일일 리스크 상태 초기화 완료")

    @staticmethod
    def reset_weekly_state() -> None:
        """
        주간 상태 초기화 (매주 월요일 실행)

        weekly_pnl을 초기화합니다.
        """
        state = RiskStateManager.load_state()
        state['weekly_pnl'] = 0.0

        RiskStateManager.save_state(state)
        Logger.print_info("🔄 주간 리스크 상태 초기화 완료")

    @staticmethod
    def calculate_weekly_pnl() -> float:
        """
        최근 7일간의 손익률 합계 계산

        Returns:
            주간 손익률 합계
        """
        all_states = RiskStateManager.load_all_states()

        # 최근 7일 날짜 생성
        today = datetime.now().date()
        week_dates = [(today - timedelta(days=i)).isoformat() for i in range(7)]

        # 최근 7일간의 daily_pnl 합계
        weekly_pnl = sum(
            all_states.get(date, {}).get('daily_pnl', 0.0)
            for date in week_dates
        )

        return weekly_pnl

    # --- Async 메서드 (PostgreSQL Repository 사용) ---

    @classmethod
    async def save_state_async(cls, state: Dict) -> None:
        """
        상태 비동기 저장 (PostgreSQL)

        Repository가 설정되지 않은 경우 동기 메서드로 폴백합니다.

        Args:
            state: 저장할 상태 딕셔너리
        """
        if cls._repository is None:
            # 폴백: JSON 파일 저장
            cls.save_state(state)
            return

        from backend.app.schemas.risk_state import RiskStateCreate

        today = date.today()
        state_data = RiskStateCreate(
            state_date=today,
            daily_pnl=Decimal(str(state.get('daily_pnl', 0.0))),
            daily_trade_count=int(state.get('daily_trade_count', 0)),
            weekly_pnl=Decimal(str(state.get('weekly_pnl', 0.0))),
            safe_mode=bool(state.get('safe_mode', False)),
            safe_mode_reason=str(state.get('safe_mode_reason', '')),
            last_trade_time=state.get('last_trade_time')
        )

        await cls._repository.save(state_data)
        Logger.print_info(f"📝 리스크 상태 저장 완료 (DB): {today}")

    @classmethod
    async def load_state_async(cls) -> Dict:
        """
        오늘 날짜 상태 비동기 로드 (PostgreSQL)

        Repository가 설정되지 않은 경우 동기 메서드로 폴백합니다.

        Returns:
            오늘 날짜의 상태 딕셔너리 (없으면 기본값)
        """
        if cls._repository is None:
            return cls.load_state()

        today = date.today()
        record = await cls._repository.load_by_date(today)

        if record:
            Logger.print_info(f"📂 리스크 상태 로드 (DB): {today}")
            return record.to_dict()

        # 기본값 반환
        default_state = {
            'daily_pnl': 0.0,
            'daily_trade_count': 0,
            'last_trade_time': None,
            'weekly_pnl': 0.0,
            'safe_mode': False,
            'safe_mode_reason': ''
        }

        Logger.print_info(f"📂 리스크 상태 없음 (DB), 기본값 사용: {today}")
        return default_state

    @classmethod
    async def calculate_weekly_pnl_async(cls) -> float:
        """
        최근 7일간의 손익률 합계 비동기 계산 (PostgreSQL)

        Returns:
            주간 손익률 합계
        """
        if cls._repository is None:
            return cls.calculate_weekly_pnl()

        weekly_pnl = await cls._repository.calculate_weekly_pnl()
        return float(weekly_pnl)
