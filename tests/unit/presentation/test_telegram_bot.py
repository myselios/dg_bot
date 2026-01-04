"""
Telegram 봇 명령어 서비스 테스트

TDD: Red → Green → Refactor
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime


class TestTelegramBotServiceInitialization:
    """TelegramBotService 초기화 테스트"""

    def test_service_creation(self):
        """서비스 생성 테스트"""
        # settings 모듈을 직접 패치 (환경변수는 이미 로드되어 있음)
        with patch('telegram_bot.settings') as mock_settings:
            mock_settings.TELEGRAM_BOT_TOKEN = 'test_token'
            mock_settings.TELEGRAM_CHAT_ID = '12345'

            from telegram_bot import TelegramBotService

            service = TelegramBotService()

            assert service.bot_token == 'test_token'
            assert service._is_running_cycle is False

    def test_parse_single_chat_id(self):
        """단일 Chat ID 파싱"""
        with patch('telegram_bot.settings') as mock_settings:
            mock_settings.TELEGRAM_BOT_TOKEN = 'test_token'
            mock_settings.TELEGRAM_CHAT_ID = '12345'

            from telegram_bot import TelegramBotService

            service = TelegramBotService()

            assert 12345 in service.allowed_chat_ids

    def test_parse_multiple_chat_ids(self):
        """여러 Chat ID 파싱 (콤마 구분)"""
        with patch('telegram_bot.settings') as mock_settings:
            mock_settings.TELEGRAM_BOT_TOKEN = 'test_token'
            mock_settings.TELEGRAM_CHAT_ID = '12345,67890,11111'

            from telegram_bot import TelegramBotService

            service = TelegramBotService()

            assert 12345 in service.allowed_chat_ids
            assert 67890 in service.allowed_chat_ids
            assert 11111 in service.allowed_chat_ids

    def test_authorization_check_valid(self):
        """유효한 Chat ID 권한 검사"""
        with patch('telegram_bot.settings') as mock_settings:
            mock_settings.TELEGRAM_BOT_TOKEN = 'test_token'
            mock_settings.TELEGRAM_CHAT_ID = '12345'

            from telegram_bot import TelegramBotService

            service = TelegramBotService()

            assert service._is_authorized(12345) is True
            assert service._is_authorized(99999) is False

    def test_authorization_check_empty_allows_all(self):
        """Chat ID 설정이 없으면 모두 허용"""
        with patch('telegram_bot.settings') as mock_settings:
            mock_settings.TELEGRAM_BOT_TOKEN = 'test_token'
            mock_settings.TELEGRAM_CHAT_ID = ''

            from telegram_bot import TelegramBotService

            service = TelegramBotService()

            assert service._is_authorized(12345) is True
            assert service._is_authorized(99999) is True


class TestTelegramBotCommands:
    """Telegram 봇 명령어 테스트"""

    @pytest.fixture
    def mock_update(self):
        """Mock Update 객체"""
        update = MagicMock()
        update.effective_chat.id = 12345
        update.message.reply_text = AsyncMock()
        return update

    @pytest.fixture
    def mock_context(self):
        """Mock Context 객체"""
        return MagicMock()

    @pytest.fixture
    def bot_service(self):
        """테스트용 봇 서비스"""
        with patch('telegram_bot.settings') as mock_settings:
            mock_settings.TELEGRAM_BOT_TOKEN = 'test_token'
            mock_settings.TELEGRAM_CHAT_ID = '12345'

            from telegram_bot import TelegramBotService
            return TelegramBotService()

    @pytest.mark.asyncio
    async def test_cmd_start_authorized(self, bot_service, mock_update, mock_context):
        """시작 명령어 - 권한 있는 사용자"""
        await bot_service._cmd_start(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "AI 트레이딩 봇" in call_args[0][0]
        assert call_args[1]['parse_mode'] == "HTML"

    @pytest.mark.asyncio
    async def test_cmd_start_unauthorized(self, bot_service, mock_update, mock_context):
        """시작 명령어 - 권한 없는 사용자"""
        mock_update.effective_chat.id = 99999  # 허용되지 않은 ID

        await bot_service._cmd_start(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        assert "권한이 없습니다" in mock_update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_help_shows_commands(self, bot_service, mock_update, mock_context):
        """도움말 명령어 - 명령어 목록 표시"""
        await bot_service._cmd_help(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "/run" in call_args
        assert "/status" in call_args
        assert "/positions" in call_args
        assert "/balance" in call_args

    @pytest.mark.asyncio
    async def test_cmd_run_prevents_duplicate_execution(self, bot_service, mock_update, mock_context):
        """트레이딩 사이클 중복 실행 방지"""
        bot_service._is_running_cycle = True

        await bot_service._cmd_run(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "이미 트레이딩 사이클이 실행 중" in call_args

    @pytest.mark.asyncio
    async def test_cmd_run_executes_trading_cycle(self, bot_service, mock_update, mock_context):
        """트레이딩 사이클 실행"""
        mock_result = {
            'status': 'success',
            'decision': 'hold',
            'confidence': 'medium',
            'reason': '시장 관망 권장'
        }

        with patch('main.execute_trading_cycle', new_callable=AsyncMock) as mock_execute:
            with patch('src.api.upbit_client.UpbitClient'):
                with patch('src.data.collector.DataCollector'):
                    mock_execute.return_value = mock_result

                    await bot_service._cmd_run(mock_update, mock_context)

                    # 최소 2번 호출됨 (시작 메시지 + 결과 메시지)
                    assert mock_update.message.reply_text.call_count >= 2

                    # 실행 후 플래그가 False로 복원되어야 함
                    assert bot_service._is_running_cycle is False

    @pytest.mark.asyncio
    async def test_cmd_status_shows_portfolio_info(self, bot_service, mock_update, mock_context):
        """상태 명령어 - 포트폴리오 정보 표시"""
        mock_status = MagicMock()
        mock_status.trading_mode.value = 'entry'
        mock_status.positions = []
        mock_status.can_open_new_position = True
        mock_status.total_current_value = 1000000  # Updated attribute name
        mock_status.krw_balance = 500000  # Updated attribute name
        mock_status.total_invested = 500000

        with patch('src.api.upbit_client.UpbitClient'):
            with patch('src.position.portfolio_manager.PortfolioManager') as mock_pm_class:
                mock_pm = MagicMock()
                mock_pm.get_portfolio_status.return_value = mock_status
                mock_pm_class.return_value = mock_pm

                await bot_service._cmd_status(mock_update, mock_context)

                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "봇 상태" in call_args
                assert "총 자산" in call_args

    @pytest.mark.asyncio
    async def test_cmd_positions_no_positions(self, bot_service, mock_update, mock_context):
        """포지션 명령어 - 포지션 없음"""
        mock_status = MagicMock()
        mock_status.positions = []

        with patch('src.api.upbit_client.UpbitClient'):
            with patch('src.position.portfolio_manager.PortfolioManager') as mock_pm_class:
                mock_pm = MagicMock()
                mock_pm.get_portfolio_status.return_value = mock_status
                mock_pm_class.return_value = mock_pm

                await bot_service._cmd_positions(mock_update, mock_context)

                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "보유 포지션 없음" in call_args

    @pytest.mark.asyncio
    async def test_cmd_positions_with_positions(self, bot_service, mock_update, mock_context):
        """포지션 명령어 - 포지션 있음"""
        mock_position = MagicMock()
        mock_position.symbol = 'BTC'
        mock_position.avg_buy_price = 50000000
        mock_position.current_price = 51000000
        mock_position.balance = 0.01
        mock_position.current_value = 510000
        mock_position.unrealized_pnl = 10000
        mock_position.profit_rate = 2.0

        mock_status = MagicMock()
        mock_status.positions = [mock_position]

        with patch('src.api.upbit_client.UpbitClient'):
            with patch('src.position.portfolio_manager.PortfolioManager') as mock_pm_class:
                mock_pm = MagicMock()
                mock_pm.get_portfolio_status.return_value = mock_status
                mock_pm_class.return_value = mock_pm

                await bot_service._cmd_positions(mock_update, mock_context)

                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "BTC" in call_args
                assert "보유 포지션 목록" in call_args


class TestEnvironmentValidation:
    """환경변수 검증 테스트"""

    def test_validate_with_all_required_vars(self):
        """모든 필수 환경변수가 있는 경우"""
        with patch.dict(os.environ, {
            'TELEGRAM_BOT_TOKEN': 'test_token',
            'UPBIT_ACCESS_KEY': 'test_key',
            'UPBIT_SECRET_KEY': 'test_secret'
        }):
            from telegram_bot import validate_environment_variables

            result = validate_environment_variables()

            assert result is True

    def test_validate_missing_telegram_token(self):
        """TELEGRAM_BOT_TOKEN이 없는 경우"""
        env_without_token = {
            'UPBIT_ACCESS_KEY': 'test_key',
            'UPBIT_SECRET_KEY': 'test_secret'
        }

        # 환경변수 초기화 후 설정
        with patch.dict(os.environ, env_without_token, clear=True):
            from telegram_bot import validate_environment_variables

            result = validate_environment_variables()

            assert result is False


class TestGracefulKiller:
    """Graceful Shutdown 테스트"""

    def test_initial_state(self):
        """초기 상태"""
        from telegram_bot import GracefulKiller

        # 새 인스턴스 생성 시 kill_now는 False
        killer = GracefulKiller()

        assert killer.kill_now is False

    def test_signal_sets_kill_flag(self):
        """시그널 수신 시 kill_now 플래그 설정"""
        from telegram_bot import GracefulKiller

        killer = GracefulKiller()

        # 시그널 핸들러 직접 호출
        killer.exit_gracefully(None, None)

        assert killer.kill_now is True
