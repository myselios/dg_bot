"""
봇 제어 API 테스트
TDD 원칙: 봇 제어 API 엔드포인트를 검증합니다.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from backend.app.api.v1.endpoints.bot_control import (
    router,
    BotStatus,
    BotControlRequest,
    ConfigUpdateRequest,
)


@pytest.mark.asyncio
class TestBotControlAPI:
    """봇 제어 API 테스트"""
    
    @pytest.mark.unit
    async def test_get_bot_status_with_existing_config(self):
        """기존 설정이 있는 경우 봇 상태 조회"""
        # Given
        mock_db = AsyncMock()
        mock_config = MagicMock()
        mock_config.value = {
            "is_running": True,
            "symbol": "KRW-ETH",
            "interval_minutes": 3,
            "last_run": "2024-01-01T12:00:00",
            "next_run": "2024-01-01T12:03:00",
        }
        
        # Mock execute() to return a result with scalar_one_or_none() that returns config
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        # When
        from backend.app.api.v1.endpoints.bot_control import get_bot_status
        status = await get_bot_status(db=mock_db)
        
        # Then
        assert isinstance(status, BotStatus)
        assert status.is_running is True
        assert status.symbol == "KRW-ETH"
        assert status.interval_minutes == 3
        assert status.last_run == "2024-01-01T12:00:00"
        assert status.next_run == "2024-01-01T12:03:00"
    
    @pytest.mark.unit
    async def test_get_bot_status_with_no_config(self):
        """설정이 없는 경우 기본값 반환"""
        # Given
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        # When
        from backend.app.api.v1.endpoints.bot_control import get_bot_status
        status = await get_bot_status(db=mock_db)
        
        # Then
        assert isinstance(status, BotStatus)
        assert status.is_running is False
        assert status.symbol == "KRW-BTC"
        assert status.interval_minutes == 5
        assert status.last_run is None
        assert status.next_run is None
    
    @pytest.mark.unit
    async def test_control_bot_start(self):
        """봇 시작 제어"""
        # Given
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        request = BotControlRequest(action="start", reason="테스트 시작")
        
        # When
        from backend.app.api.v1.endpoints.bot_control import control_bot
        response = await control_bot(request=request, db=mock_db)
        
        # Then
        assert response["status"] == "success"
        assert "start" in response["message"]
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    
    @pytest.mark.unit
    async def test_control_bot_stop(self):
        """봇 중지 제어"""
        # Given
        mock_db = AsyncMock()
        mock_config = MagicMock()
        mock_config.value = {"is_running": True}
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_db.execute = AsyncMock(return_value=mock_result)
        request = BotControlRequest(action="stop", reason="테스트 중지")
        
        # When
        from backend.app.api.v1.endpoints.bot_control import control_bot
        response = await control_bot(request=request, db=mock_db)
        
        # Then
        assert response["status"] == "success"
        assert "stop" in response["message"]
        assert mock_config.value["is_running"] is False
        mock_db.commit.assert_called_once()
    
    @pytest.mark.unit
    async def test_control_bot_pause(self):
        """봇 일시정지 제어"""
        # Given
        mock_db = AsyncMock()
        mock_config = MagicMock()
        mock_config.value = {"is_running": True}
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_db.execute = AsyncMock(return_value=mock_result)
        request = BotControlRequest(action="pause")
        
        # When
        from backend.app.api.v1.endpoints.bot_control import control_bot
        response = await control_bot(request=request, db=mock_db)
        
        # Then
        assert response["status"] == "success"
        assert "pause" in response["message"]
        assert mock_config.value["is_running"] is False
        mock_db.commit.assert_called_once()
    
    @pytest.mark.unit
    async def test_control_bot_invalid_action(self):
        """유효하지 않은 제어 명령"""
        # Given
        mock_db = AsyncMock()
        request = BotControlRequest(action="invalid_action")
        
        # When & Then
        from backend.app.api.v1.endpoints.bot_control import control_bot
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            await control_bot(request=request, db=mock_db)
        
        assert exc_info.value.status_code == 400
        assert "유효하지 않은" in exc_info.value.detail
    
    @pytest.mark.unit
    async def test_get_config_existing_key(self):
        """기존 설정 조회"""
        # Given
        mock_db = AsyncMock()
        mock_config = MagicMock()
        mock_config.key = "test_key"
        mock_config.value = {"param1": "value1", "param2": 123}
        mock_config.description = "테스트 설정"
        mock_config.updated_at = datetime(2024, 1, 1, 12, 0, 0)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        # When
        from backend.app.api.v1.endpoints.bot_control import get_config
        response = await get_config(key="test_key", db=mock_db)
        
        # Then
        assert response["key"] == "test_key"
        assert response["value"] == {"param1": "value1", "param2": 123}
        assert response["description"] == "테스트 설정"
        assert response["updated_at"] == "2024-01-01T12:00:00"
    
    @pytest.mark.unit
    async def test_get_config_non_existing_key(self):
        """존재하지 않는 설정 조회"""
        # Given
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        # When & Then
        from backend.app.api.v1.endpoints.bot_control import get_config
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            await get_config(key="non_existing_key", db=mock_db)
        
        assert exc_info.value.status_code == 404
        assert "찾을 수 없습니다" in exc_info.value.detail
    
    @pytest.mark.unit
    async def test_update_config_new_key(self):
        """새로운 설정 추가"""
        # Given
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        request = ConfigUpdateRequest(
            key="new_config",
            value={"param1": "value1"},
            description="새 설정"
        )
        
        # When
        from backend.app.api.v1.endpoints.bot_control import update_config
        response = await update_config(request=request, db=mock_db)
        
        # Then
        assert response["status"] == "success"
        assert "new_config" in response["message"]
        assert "업데이트" in response["message"]
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    
    @pytest.mark.unit
    async def test_update_config_existing_key(self):
        """기존 설정 업데이트"""
        # Given
        mock_db = AsyncMock()
        mock_config = MagicMock()
        mock_config.key = "existing_config"
        mock_config.value = {"old_param": "old_value"}
        mock_config.description = "기존 설명"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_db.execute = AsyncMock(return_value=mock_result)
        request = ConfigUpdateRequest(
            key="existing_config",
            value={"new_param": "new_value"},
            description="새 설명"
        )
        
        # When
        from backend.app.api.v1.endpoints.bot_control import update_config
        response = await update_config(request=request, db=mock_db)
        
        # Then
        assert response["status"] == "success"
        assert "existing_config" in response["message"]
        assert mock_config.value == {"new_param": "new_value"}
        assert mock_config.description == "새 설명"
        mock_db.commit.assert_called_once()
    
    @pytest.mark.unit
    async def test_update_config_without_description(self):
        """설명 없이 설정 업데이트"""
        # Given
        mock_db = AsyncMock()
        mock_config = MagicMock()
        mock_config.key = "test_config"
        mock_config.value = {"old": "value"}
        mock_config.description = "기존 설명"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_db.execute = AsyncMock(return_value=mock_result)
        request = ConfigUpdateRequest(
            key="test_config",
            value={"new": "value"},
            description=None
        )
        
        # When
        from backend.app.api.v1.endpoints.bot_control import update_config
        response = await update_config(request=request, db=mock_db)
        
        # Then
        assert response["status"] == "success"
        assert mock_config.value == {"new": "value"}
        assert mock_config.description == "기존 설명"  # 변경되지 않음
        mock_db.commit.assert_called_once()


@pytest.mark.asyncio
class TestBotControlModels:
    """봇 제어 모델 테스트"""
    
    @pytest.mark.unit
    def test_bot_status_model(self):
        """BotStatus 모델 생성"""
        # When
        status = BotStatus(
            is_running=True,
            symbol="KRW-ETH",
            interval_minutes=3,
            last_run="2024-01-01T12:00:00",
            next_run="2024-01-01T12:03:00"
        )
        
        # Then
        assert status.is_running is True
        assert status.symbol == "KRW-ETH"
        assert status.interval_minutes == 3
    
    @pytest.mark.unit
    def test_bot_control_request_model(self):
        """BotControlRequest 모델 생성"""
        # When
        request = BotControlRequest(
            action="start",
            reason="테스트"
        )
        
        # Then
        assert request.action == "start"
        assert request.reason == "테스트"
    
    @pytest.mark.unit
    def test_config_update_request_model(self):
        """ConfigUpdateRequest 모델 생성"""
        # When
        request = ConfigUpdateRequest(
            key="test_key",
            value={"param": "value"},
            description="설명"
        )
        
        # Then
        assert request.key == "test_key"
        assert request.value == {"param": "value"}
        assert request.description == "설명"

