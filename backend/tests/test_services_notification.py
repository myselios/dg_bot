"""
알림 서비스 테스트
TDD 원칙: Telegram 알림 로직을 검증합니다.
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch
from decimal import Decimal

from backend.app.services.notification import TelegramNotifier, notifier


@pytest.mark.asyncio
class TestTelegramNotifier:
    """TelegramNotifier 클래스 테스트"""
    
    async def test_notifier_disabled_by_default(self):
        """
        Given: Telegram 설정이 없는 상태
        When: TelegramNotifier 초기화
        Then: enabled가 False여야 함
        """
        # Given & When
        test_notifier = TelegramNotifier()
        
        # Then
        # 환경 변수가 설정되지 않으면 비활성화
        result = await test_notifier.send_message("테스트")
        assert result == False
    
    @patch('backend.app.services.notification.settings')
    async def test_send_message_when_disabled(self, mock_settings):
        """
        Given: Telegram이 비활성화된 상태
        When: send_message 호출
        Then: False 반환하고 실제 전송하지 않음
        """
        # Given
        mock_settings.TELEGRAM_ENABLED = False
        test_notifier = TelegramNotifier()
        
        # When
        result = await test_notifier.send_message("테스트 메시지")
        
        # Then
        assert result == False
    
    @patch('backend.app.services.notification.Bot')
    @patch('backend.app.services.notification.settings')
    async def test_send_message_success(self, mock_settings, mock_bot_class):
        """
        Given: Telegram이 활성화된 상태
        When: send_message 호출
        Then: 메시지 전송 성공
        """
        # Given
        mock_settings.TELEGRAM_ENABLED = True
        mock_settings.TELEGRAM_BOT_TOKEN = "test_token"
        mock_settings.TELEGRAM_CHAT_ID = "test_chat_id"
        
        mock_bot_instance = AsyncMock()
        mock_bot_class.return_value = mock_bot_instance
        
        test_notifier = TelegramNotifier()
        test_notifier._bot = mock_bot_instance
        test_notifier.enabled = True
        
        # When
        result = await test_notifier.send_message("테스트 메시지")
        
        # Then
        assert result == True
        mock_bot_instance.send_message.assert_called_once()
    
    @patch('backend.app.services.notification.Bot')
    @patch('backend.app.services.notification.settings')
    async def test_notify_trade(self, mock_settings, mock_bot_class):
        """
        Given: 거래 정보
        When: notify_trade 호출
        Then: 포맷팅된 거래 알림 전송
        """
        # Given
        mock_settings.TELEGRAM_ENABLED = True
        mock_settings.TELEGRAM_BOT_TOKEN = "test_token"
        mock_settings.TELEGRAM_CHAT_ID = "test_chat_id"
        
        mock_bot_instance = AsyncMock()
        mock_bot_class.return_value = mock_bot_instance
        
        test_notifier = TelegramNotifier()
        test_notifier._bot = mock_bot_instance
        test_notifier.enabled = True
        
        # When
        result = await test_notifier.notify_trade(
            symbol="KRW-BTC",
            side="buy",
            price=Decimal("95000000"),
            amount=Decimal("0.001"),
            total=Decimal("95000"),
            reason="RSI 과매도 구간",
        )
        
        # Then
        assert result == True
        mock_bot_instance.send_message.assert_called_once()
        
        # 호출된 메시지 내용 확인
        call_args = mock_bot_instance.send_message.call_args
        message = call_args.kwargs["text"]
        assert "매수" in message
        assert "KRW-BTC" in message
        assert "95,000,000" in message
        assert "RSI 과매도 구간" in message
    
    @patch('backend.app.services.notification.Bot')
    @patch('backend.app.services.notification.settings')
    async def test_notify_error(self, mock_settings, mock_bot_class):
        """
        Given: 에러 정보
        When: notify_error 호출
        Then: 포맷팅된 에러 알림 전송
        """
        # Given
        mock_settings.TELEGRAM_ENABLED = True
        mock_settings.TELEGRAM_BOT_TOKEN = "test_token"
        mock_settings.TELEGRAM_CHAT_ID = "test_chat_id"
        
        mock_bot_instance = AsyncMock()
        mock_bot_class.return_value = mock_bot_instance
        
        test_notifier = TelegramNotifier()
        test_notifier._bot = mock_bot_instance
        test_notifier.enabled = True
        
        # When
        result = await test_notifier.notify_error(
            error_type="APIError",
            error_message="Upbit API 타임아웃",
            context={"symbol": "KRW-BTC", "attempt": 3},
        )
        
        # Then
        assert result == True
        call_args = mock_bot_instance.send_message.call_args
        message = call_args.kwargs["text"]
        assert "에러 발생" in message
        assert "APIError" in message
        assert "타임아웃" in message
    
    @patch('backend.app.services.notification.Bot')
    @patch('backend.app.services.notification.settings')
    async def test_notify_daily_report(self, mock_settings, mock_bot_class):
        """
        Given: 일일 리포트 데이터
        When: notify_daily_report 호출
        Then: 포맷팅된 리포트 전송
        """
        # Given
        mock_settings.TELEGRAM_ENABLED = True
        mock_settings.TELEGRAM_BOT_TOKEN = "test_token"
        mock_settings.TELEGRAM_CHAT_ID = "test_chat_id"
        
        mock_bot_instance = AsyncMock()
        mock_bot_class.return_value = mock_bot_instance
        
        test_notifier = TelegramNotifier()
        test_notifier._bot = mock_bot_instance
        test_notifier.enabled = True
        
        # When
        result = await test_notifier.notify_daily_report(
            total_trades=10,
            profit_loss=Decimal("150000"),
            profit_rate=Decimal("3.5"),
            current_value=Decimal("5150000"),
        )
        
        # Then
        assert result == True
        call_args = mock_bot_instance.send_message.call_args
        message = call_args.kwargs["text"]
        assert "일일 트레이딩 리포트" in message
        assert "+3.5" in message
        assert "10회" in message
        assert "📈" in message  # 수익 이모지
    
    @patch('backend.app.services.notification.Bot')
    @patch('backend.app.services.notification.settings')
    async def test_notify_daily_report_loss(self, mock_settings, mock_bot_class):
        """
        Given: 손실 발생한 일일 리포트
        When: notify_daily_report 호출
        Then: 손실 이모지와 함께 리포트 전송
        """
        # Given
        mock_settings.TELEGRAM_ENABLED = True
        mock_settings.TELEGRAM_BOT_TOKEN = "test_token"
        mock_settings.TELEGRAM_CHAT_ID = "test_chat_id"
        
        mock_bot_instance = AsyncMock()
        mock_bot_class.return_value = mock_bot_instance
        
        test_notifier = TelegramNotifier()
        test_notifier._bot = mock_bot_instance
        test_notifier.enabled = True
        
        # When
        result = await test_notifier.notify_daily_report(
            total_trades=5,
            profit_loss=Decimal("-50000"),
            profit_rate=Decimal("-1.2"),
            current_value=Decimal("4950000"),
        )
        
        # Then
        assert result == True
        call_args = mock_bot_instance.send_message.call_args
        message = call_args.kwargs["text"]
        assert "-1.2" in message
        assert "📉" in message  # 손실 이모지
    
    @patch('backend.app.services.notification.Bot')
    @patch('backend.app.services.notification.settings')
    async def test_notify_bot_status(self, mock_settings, mock_bot_class):
        """
        Given: 봇 상태 변경 정보
        When: notify_bot_status 호출
        Then: 상태 알림 전송
        """
        # Given
        mock_settings.TELEGRAM_ENABLED = True
        mock_settings.TELEGRAM_BOT_TOKEN = "test_token"
        mock_settings.TELEGRAM_CHAT_ID = "test_chat_id"
        
        mock_bot_instance = AsyncMock()
        mock_bot_class.return_value = mock_bot_instance
        
        test_notifier = TelegramNotifier()
        test_notifier._bot = mock_bot_instance
        test_notifier.enabled = True
        
        # When
        result = await test_notifier.notify_bot_status(
            status="started",
            message="자동 트레이딩 시작됨",
        )
        
        # Then
        assert result == True
        call_args = mock_bot_instance.send_message.call_args
        message = call_args.kwargs["text"]
        assert "봇 상태 변경" in message
        assert "STARTED" in message
        assert "▶️" in message



