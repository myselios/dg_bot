"""
State Persistence 전용 테스트

리스크 관리 상태의 영속성을 검증합니다:
- JSON 파일 저장/로드
- 프로그램 재시작 시뮬레이션
- 일일/주간 리셋
- Circuit Breaker와의 통합

작성일: 2026-01-02
"""
import pytest
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.risk.state_manager import RiskStateManager
from src.risk.manager import RiskManager, RiskLimits


class TestRiskStateManager:
    """RiskStateManager 단위 테스트"""

    @pytest.fixture(autouse=True)
    def setup_teardown(self, tmp_path):
        """각 테스트 전후 설정"""
        # 임시 파일 경로로 STATE_FILE 교체
        self.original_state_file = RiskStateManager.STATE_FILE
        RiskStateManager.STATE_FILE = tmp_path / "risk_state.json"
        yield
        # 원래 경로 복원
        RiskStateManager.STATE_FILE = self.original_state_file

    def test_save_and_load_state(self):
        """상태 저장 및 로드 테스트"""
        # Given: 저장할 상태
        state = {
            'daily_pnl': -5.0,
            'daily_trade_count': 3,
            'last_trade_time': '2026-01-02T10:00:00',
            'weekly_pnl': -8.0,
            'safe_mode': False,
            'safe_mode_reason': ''
        }

        # When: 상태 저장 후 로드
        RiskStateManager.save_state(state)
        loaded_state = RiskStateManager.load_state()

        # Then: 저장된 값과 일치
        assert loaded_state['daily_pnl'] == -5.0
        assert loaded_state['daily_trade_count'] == 3
        assert loaded_state['weekly_pnl'] == -8.0
        assert loaded_state['safe_mode'] == False

    def test_load_state_returns_default_when_empty(self):
        """상태 파일 없을 때 기본값 반환 테스트"""
        # Given: 파일 없음 (자동으로 빈 상태)

        # When: 상태 로드
        state = RiskStateManager.load_state()

        # Then: 기본값 반환
        assert state['daily_pnl'] == 0.0
        assert state['daily_trade_count'] == 0
        assert state['weekly_pnl'] == 0.0
        assert state['safe_mode'] == False

    def test_state_persists_across_date_keys(self):
        """날짜별 상태 분리 저장 테스트"""
        # Given: 오늘 날짜의 상태 저장
        today = datetime.now().date().isoformat()
        state1 = {
            'daily_pnl': -3.0,
            'daily_trade_count': 2,
            'weekly_pnl': -3.0,
            'safe_mode': False,
            'safe_mode_reason': ''
        }
        RiskStateManager.save_state(state1)

        # When: 모든 상태 로드
        all_states = RiskStateManager.load_all_states()

        # Then: 오늘 날짜 키로 저장됨
        assert today in all_states
        assert all_states[today]['daily_pnl'] == -3.0

    def test_reset_daily_state(self):
        """일일 상태 리셋 테스트"""
        # Given: 기존 상태
        state = {
            'daily_pnl': -5.0,
            'daily_trade_count': 3,
            'weekly_pnl': -8.0,
            'safe_mode': True,
            'safe_mode_reason': '일일 손실 한도 초과'
        }
        RiskStateManager.save_state(state)

        # When: 일일 상태 리셋
        RiskStateManager.reset_daily_state()
        loaded_state = RiskStateManager.load_state()

        # Then: daily 값만 초기화, weekly 유지
        assert loaded_state['daily_pnl'] == 0.0
        assert loaded_state['daily_trade_count'] == 0
        assert loaded_state['weekly_pnl'] == -8.0  # 유지됨
        assert loaded_state['safe_mode'] == False

    def test_reset_weekly_state(self):
        """주간 상태 리셋 테스트"""
        # Given: 기존 상태
        state = {
            'daily_pnl': -5.0,
            'daily_trade_count': 3,
            'weekly_pnl': -15.0,
            'safe_mode': False,
            'safe_mode_reason': ''
        }
        RiskStateManager.save_state(state)

        # When: 주간 상태 리셋
        RiskStateManager.reset_weekly_state()
        loaded_state = RiskStateManager.load_state()

        # Then: weekly_pnl만 초기화
        assert loaded_state['daily_pnl'] == -5.0  # 유지됨
        assert loaded_state['weekly_pnl'] == 0.0

    def test_old_data_cleanup(self):
        """7일 이전 데이터 자동 삭제 테스트"""
        # Given: 8일 전 ~ 오늘까지 데이터 저장
        for i in range(10):
            date = (datetime.now() - timedelta(days=i)).date().isoformat()
            # 직접 파일에 저장 (save_state의 cleanup 로직 테스트)
            all_states = RiskStateManager.load_all_states()
            all_states[date] = {
                'daily_pnl': float(-i),
                'daily_trade_count': i,
                'weekly_pnl': 0.0,
                'safe_mode': False,
                'safe_mode_reason': ''
            }
            RiskStateManager.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(RiskStateManager.STATE_FILE, 'w') as f:
                json.dump(all_states, f)

        # When: 새 상태 저장 (cleanup 트리거)
        RiskStateManager.save_state({
            'daily_pnl': -1.0,
            'daily_trade_count': 1,
            'weekly_pnl': -1.0,
            'safe_mode': False,
            'safe_mode_reason': ''
        })
        all_states = RiskStateManager.load_all_states()

        # Then: 8일 이상 된 데이터 삭제됨
        eight_days_ago = (datetime.now() - timedelta(days=8)).date().isoformat()
        assert eight_days_ago not in all_states
        # 7일 이내 데이터는 유지
        assert len(all_states) <= 8  # 오늘 + 최대 7일

    def test_calculate_weekly_pnl(self):
        """주간 손익 계산 테스트"""
        # Given: 최근 7일간 각 날짜별 daily_pnl 저장
        for i in range(7):
            date = (datetime.now() - timedelta(days=i)).date().isoformat()
            all_states = RiskStateManager.load_all_states()
            all_states[date] = {
                'daily_pnl': -1.0,  # 매일 -1%
                'daily_trade_count': 1,
                'weekly_pnl': 0.0,
                'safe_mode': False,
                'safe_mode_reason': ''
            }
            RiskStateManager.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(RiskStateManager.STATE_FILE, 'w') as f:
                json.dump(all_states, f)

        # When: 주간 손익 계산
        weekly_pnl = RiskStateManager.calculate_weekly_pnl()

        # Then: 7일 합계 = -7%
        assert weekly_pnl == -7.0


class TestRiskManagerWithPersistence:
    """RiskManager의 State Persistence 통합 테스트"""

    @pytest.fixture(autouse=True)
    def setup_teardown(self, tmp_path):
        """각 테스트 전후 설정"""
        # 임시 파일 경로로 STATE_FILE 교체
        self.original_state_file = RiskStateManager.STATE_FILE
        RiskStateManager.STATE_FILE = tmp_path / "risk_state.json"
        yield
        # 원래 경로 복원
        RiskStateManager.STATE_FILE = self.original_state_file

    def test_risk_manager_loads_persisted_state(self):
        """RiskManager가 저장된 상태를 로드하는지 테스트"""
        # Given: 이전에 저장된 상태
        state = {
            'daily_pnl': -5.0,
            'daily_trade_count': 3,
            'last_trade_time': datetime.now().isoformat(),
            'weekly_pnl': -8.0,
            'safe_mode': False,
            'safe_mode_reason': ''
        }
        RiskStateManager.save_state(state)

        # When: RiskManager 생성 (persist_state=True)
        risk_manager = RiskManager(
            limits=RiskLimits(
                stop_loss_pct=-5.0,
                take_profit_pct=10.0,
                daily_loss_limit_pct=-10.0,
            ),
            persist_state=True
        )

        # Then: 저장된 상태가 로드됨
        assert risk_manager.daily_pnl == -5.0
        assert risk_manager.daily_trade_count == 3

    def test_risk_manager_saves_state_on_trade(self):
        """거래 기록 시 상태 저장 테스트"""
        # Given: RiskManager 생성
        risk_manager = RiskManager(
            limits=RiskLimits(
                stop_loss_pct=-5.0,
                take_profit_pct=10.0,
                daily_loss_limit_pct=-10.0,
            ),
            persist_state=True
        )

        # When: 거래 기록
        risk_manager.record_trade(-3.0)  # -3% 손실

        # Then: 상태가 파일에 저장됨
        saved_state = RiskStateManager.load_state()
        assert saved_state['daily_pnl'] == -3.0
        assert saved_state['daily_trade_count'] == 1

    def test_circuit_breaker_with_persistence(self):
        """Circuit Breaker가 저장된 상태를 기반으로 작동하는지 테스트"""
        # Given: 일일 손실 한도에 근접한 상태 저장
        state = {
            'daily_pnl': -9.0,  # -10% 한도에 근접
            'daily_trade_count': 5,
            'last_trade_time': datetime.now().isoformat(),
            'weekly_pnl': -9.0,
            'safe_mode': False,
            'safe_mode_reason': ''
        }
        RiskStateManager.save_state(state)

        # When: 새 RiskManager 생성 (프로그램 재시작 시뮬레이션)
        risk_manager = RiskManager(
            limits=RiskLimits(
                stop_loss_pct=-5.0,
                take_profit_pct=10.0,
                daily_loss_limit_pct=-10.0,
            ),
            persist_state=True
        )

        # 추가 손실 발생 시 Circuit Breaker 작동 확인
        # daily_pnl = -9% + (-2%) = -11% (한도 초과)
        result = risk_manager.check_circuit_breaker()

        # Then: 아직 한도 초과 아님 (현재 -9%)
        # check_circuit_breaker는 'allowed' 키 반환
        assert result['allowed'] is True

        # 추가 손실 기록
        risk_manager.record_trade(-2.0)

        # 다시 체크
        result = risk_manager.check_circuit_breaker()
        # -11%로 한도 초과
        assert result['allowed'] is False
        assert '일일 손실 한도' in result['reason'] or 'daily_loss_limit' in result['reason'].lower()

    def test_state_persists_after_restart_simulation(self):
        """프로그램 재시작 시뮬레이션 테스트"""
        # Given: 첫 번째 RiskManager 인스턴스에서 거래 기록
        risk_manager_1 = RiskManager(
            limits=RiskLimits(daily_loss_limit_pct=-10.0),
            persist_state=True
        )
        risk_manager_1.record_trade(-3.0)
        risk_manager_1.record_trade(-2.0)
        # daily_pnl = -5%, daily_trade_count = 2

        # When: "프로그램 재시작" - 새 RiskManager 인스턴스 생성
        risk_manager_2 = RiskManager(
            limits=RiskLimits(daily_loss_limit_pct=-10.0),
            persist_state=True
        )

        # Then: 상태가 유지됨
        assert risk_manager_2.daily_pnl == -5.0
        assert risk_manager_2.daily_trade_count == 2

        # 추가 거래 시 누적됨
        risk_manager_2.record_trade(-4.0)
        assert risk_manager_2.daily_pnl == -9.0
        assert risk_manager_2.daily_trade_count == 3

    def test_no_persistence_mode(self):
        """persist_state=False일 때 파일 미사용 테스트"""
        # Given: 저장된 상태
        state = {
            'daily_pnl': -5.0,
            'daily_trade_count': 3,
            'weekly_pnl': -5.0,
            'safe_mode': False,
            'safe_mode_reason': ''
        }
        RiskStateManager.save_state(state)

        # When: persist_state=False로 RiskManager 생성
        risk_manager = RiskManager(
            limits=RiskLimits(),
            persist_state=False
        )

        # Then: 저장된 상태를 로드하지 않음 (기본값)
        assert risk_manager.daily_pnl == 0.0
        assert risk_manager.daily_trade_count == 0


class TestEdgeCases:
    """엣지 케이스 테스트"""

    @pytest.fixture(autouse=True)
    def setup_teardown(self, tmp_path):
        """각 테스트 전후 설정"""
        self.original_state_file = RiskStateManager.STATE_FILE
        RiskStateManager.STATE_FILE = tmp_path / "risk_state.json"
        yield
        RiskStateManager.STATE_FILE = self.original_state_file

    def test_corrupted_json_file(self):
        """손상된 JSON 파일 처리 테스트"""
        # Given: 손상된 JSON 파일
        RiskStateManager.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(RiskStateManager.STATE_FILE, 'w') as f:
            f.write("{ invalid json }")

        # When: 상태 로드
        state = RiskStateManager.load_state()

        # Then: 기본값 반환 (에러 핸들링)
        assert state['daily_pnl'] == 0.0

    def test_missing_keys_in_saved_state(self):
        """저장된 상태에 키가 누락된 경우"""
        # Given: 일부 키가 누락된 상태
        today = datetime.now().date().isoformat()
        RiskStateManager.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(RiskStateManager.STATE_FILE, 'w') as f:
            json.dump({
                today: {
                    'daily_pnl': -3.0,
                    # 'daily_trade_count' 누락
                    'weekly_pnl': -3.0
                }
            }, f)

        # When: 상태 로드
        state = RiskStateManager.load_state()

        # Then: 존재하는 키는 로드됨
        assert state['daily_pnl'] == -3.0
        # 누락된 키는 기본값 사용 필요 (get 사용 시)
        assert state.get('daily_trade_count', 0) == 0

    def test_concurrent_save_simulation(self):
        """동시 저장 시뮬레이션 (단일 프로세스)"""
        # Given: 여러 번의 연속 저장
        for i in range(5):
            state = {
                'daily_pnl': float(-i),
                'daily_trade_count': i,
                'weekly_pnl': float(-i),
                'safe_mode': False,
                'safe_mode_reason': ''
            }
            RiskStateManager.save_state(state)

        # When: 최종 상태 로드
        final_state = RiskStateManager.load_state()

        # Then: 마지막 저장된 값
        assert final_state['daily_pnl'] == -4.0
        assert final_state['daily_trade_count'] == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
