"""
봇 제어 API 테스트
TDD 원칙: 봇 제어 로직의 동작을 검증합니다.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.bot_config import BotConfig


@pytest.mark.asyncio
class TestBotControlAPI:
    """봇 제어 API 테스트 클래스"""
    
    async def test_get_bot_status_default(self, client: AsyncClient):
        """
        Given: 초기 상태 (설정 없음)
        When: GET /api/v1/bot/status 요청
        Then: 기본 설정 반환
        """
        response = await client.get("/api/v1/bot/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_running"] == False
        assert data["symbol"] == "KRW-BTC"
        assert data["interval_minutes"] == 5
    
    async def test_control_bot_start(self, client: AsyncClient):
        """
        Given: 봇이 중지된 상태
        When: POST /api/v1/bot/control (action=start)
        Then: 봇이 시작되고 성공 메시지 반환
        """
        response = await client.post(
            "/api/v1/bot/control",
            json={"action": "start", "reason": "테스트 시작"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "start" in data["message"]
    
    async def test_control_bot_stop(self, client: AsyncClient):
        """
        Given: 봇이 실행 중인 상태
        When: POST /api/v1/bot/control (action=stop)
        Then: 봇이 중지되고 성공 메시지 반환
        """
        # 봇 시작
        await client.post(
            "/api/v1/bot/control",
            json={"action": "start"},
        )
        
        # 봇 중지
        response = await client.post(
            "/api/v1/bot/control",
            json={"action": "stop", "reason": "테스트 중지"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "stop" in data["message"]
    
    async def test_control_bot_invalid_action(self, client: AsyncClient):
        """
        Given: 유효하지 않은 action
        When: POST /api/v1/bot/control (action=invalid)
        Then: 400 Bad Request 반환
        """
        response = await client.post(
            "/api/v1/bot/control",
            json={"action": "invalid"},
        )
        
        assert response.status_code == 400
        assert "유효하지 않은" in response.json()["detail"]
    
    async def test_get_config(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ):
        """
        Given: 저장된 설정
        When: GET /api/v1/bot/config/{key} 요청
        Then: 해당 설정 반환
        """
        # 설정 저장
        config = BotConfig(
            key="test_config",
            value={"enabled": True, "interval": 10},
            description="테스트 설정",
        )
        async_session.add(config)
        await async_session.commit()
        
        # 설정 조회
        response = await client.get("/api/v1/bot/config/test_config")
        
        assert response.status_code == 200
        data = response.json()
        assert data["key"] == "test_config"
        assert data["value"]["enabled"] == True
        assert data["value"]["interval"] == 10
    
    async def test_get_config_not_found(self, client: AsyncClient):
        """
        Given: 존재하지 않는 설정 키
        When: GET /api/v1/bot/config/{key} 요청
        Then: 404 Not Found 반환
        """
        response = await client.get("/api/v1/bot/config/nonexistent")
        
        assert response.status_code == 404
        assert "찾을 수 없습니다" in response.json()["detail"]
    
    async def test_update_config_new(self, client: AsyncClient):
        """
        Given: 새로운 설정
        When: POST /api/v1/bot/config 요청
        Then: 설정이 생성되고 성공 메시지 반환
        """
        response = await client.post(
            "/api/v1/bot/config",
            json={
                "key": "new_config",
                "value": {"test": "value"},
                "description": "새 설정",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "업데이트" in data["message"]
    
    async def test_update_config_existing(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ):
        """
        Given: 기존 설정
        When: POST /api/v1/bot/config으로 업데이트
        Then: 설정이 변경되고 성공 메시지 반환
        """
        # 기존 설정 생성
        config = BotConfig(
            key="update_config",
            value={"old": "value"},
            description="기존 설정",
        )
        async_session.add(config)
        await async_session.commit()
        
        # 설정 업데이트
        response = await client.post(
            "/api/v1/bot/config",
            json={
                "key": "update_config",
                "value": {"new": "value"},
                "description": "업데이트된 설정",
            },
        )
        
        assert response.status_code == 200
        
        # 업데이트 확인
        get_response = await client.get("/api/v1/bot/config/update_config")
        data = get_response.json()
        assert data["value"]["new"] == "value"
        assert "old" not in data["value"]
    
    async def test_bot_status_after_start(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ):
        """
        Given: 봇 시작 명령 실행
        When: GET /api/v1/bot/status 요청
        Then: is_running이 true로 변경되어야 함
        """
        # 봇 시작
        await client.post(
            "/api/v1/bot/control",
            json={"action": "start"},
        )
        
        # 상태 확인
        response = await client.get("/api/v1/bot/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_running"] == True



