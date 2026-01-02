"""
Telegram 봇 명령어 서비스

Telegram을 통한 수동 트레이딩 제어 및 상태 확인 기능을 제공합니다.

지원 명령어:
    /run - 트레이딩 사이클 수동 실행
    /status - 현재 봇 상태 및 포트폴리오 확인
    /positions - 보유 포지션 목록
    /help - 도움말

사용법:
    python telegram_bot.py

중지:
    Ctrl + C (SIGINT)
"""
import asyncio
import signal
import sys
import logging
import os
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 로그 디렉토리 생성
log_dir = project_root / "logs" / "telegram_bot"
log_dir.mkdir(parents=True, exist_ok=True)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'telegram_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# .env 파일 로드
if os.path.exists(".env"):
    from dotenv import load_dotenv
    load_dotenv()

from backend.app.core.config import settings


class TelegramBotService:
    """Telegram 봇 명령어 처리 서비스"""

    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.allowed_chat_ids = self._parse_allowed_chat_ids()
        self._application = None
        self._is_running_cycle = False  # 중복 실행 방지

    def _parse_allowed_chat_ids(self) -> set:
        """허용된 채팅 ID 목록 파싱"""
        chat_id = settings.TELEGRAM_CHAT_ID
        if not chat_id:
            return set()

        # 단일 ID 또는 콤마로 구분된 여러 ID 지원
        if ',' in str(chat_id):
            return set(int(cid.strip()) for cid in str(chat_id).split(','))
        return {int(chat_id)}

    def _is_authorized(self, chat_id: int) -> bool:
        """채팅 ID가 허용된 사용자인지 확인"""
        if not self.allowed_chat_ids:
            return True  # 설정이 없으면 모두 허용 (보안 주의!)
        return chat_id in self.allowed_chat_ids

    async def start(self):
        """봇 시작"""
        from telegram import Update
        from telegram.ext import Application, CommandHandler, ContextTypes

        if not self.bot_token:
            logger.error("❌ TELEGRAM_BOT_TOKEN이 설정되지 않았습니다.")
            return

        # Application 생성
        self._application = Application.builder().token(self.bot_token).build()

        # 명령어 핸들러 등록
        self._application.add_handler(CommandHandler("start", self._cmd_start))
        self._application.add_handler(CommandHandler("help", self._cmd_help))
        self._application.add_handler(CommandHandler("run", self._cmd_run))
        self._application.add_handler(CommandHandler("status", self._cmd_status))
        self._application.add_handler(CommandHandler("positions", self._cmd_positions))
        self._application.add_handler(CommandHandler("balance", self._cmd_balance))

        # 봇 정보 출력
        logger.info("=" * 60)
        logger.info("🤖 Telegram 봇 명령어 서비스 시작")
        logger.info("=" * 60)
        logger.info(f"허용된 Chat ID: {self.allowed_chat_ids or '모든 사용자'}")
        logger.info("=" * 60)

        # 봇 시작 (polling 모드)
        await self._application.initialize()
        await self._application.start()
        await self._application.updater.start_polling(drop_pending_updates=True)

        logger.info("✅ Telegram 봇이 실행 중입니다... (Ctrl+C로 종료)")

    async def stop(self):
        """봇 종료"""
        if self._application:
            await self._application.updater.stop()
            await self._application.stop()
            await self._application.shutdown()
            logger.info("✅ Telegram 봇이 안전하게 종료되었습니다.")

    # =========================================================================
    # 명령어 핸들러
    # =========================================================================

    async def _cmd_start(self, update, context):
        """시작 명령어"""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ 권한이 없습니다.")
            return

        message = """
🤖 <b>AI 트레이딩 봇</b>

안녕하세요! 트레이딩 봇 명령어 서비스입니다.

<b>사용 가능한 명령어:</b>
/run - 트레이딩 사이클 수동 실행
/status - 현재 봇 상태 확인
/positions - 보유 포지션 목록
/balance - 잔고 확인
/help - 도움말

🕐 <b>현재 시각:</b> {time}
        """.format(time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        await update.message.reply_text(message, parse_mode="HTML")

    async def _cmd_help(self, update, context):
        """도움말 명령어"""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ 권한이 없습니다.")
            return

        message = """
📖 <b>명령어 도움말</b>

━━━━━━━━━━━━━━━━━━━━
<b>🚀 트레이딩 제어</b>
━━━━━━━━━━━━━━━━━━━━
/run - 트레이딩 사이클 수동 실행
  • 멀티코인 스캐닝 → 백테스팅 → AI 분석 → 거래 실행
  • 이미 실행 중이면 중복 실행 방지

━━━━━━━━━━━━━━━━━━━━
<b>📊 상태 확인</b>
━━━━━━━━━━━━━━━━━━━━
/status - 봇 및 시스템 상태 확인
/positions - 현재 보유 포지션 목록
/balance - KRW 및 코인 잔고 확인

━━━━━━━━━━━━━━━━━━━━
<b>ℹ️ 기타</b>
━━━━━━━━━━━━━━━━━━━━
/start - 시작 인사 및 명령어 목록
/help - 이 도움말 표시

⚠️ <b>주의:</b> /run 명령어는 실제 거래를 실행합니다.
        """

        await update.message.reply_text(message, parse_mode="HTML")

    async def _cmd_run(self, update, context):
        """트레이딩 사이클 수동 실행"""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ 권한이 없습니다.")
            return

        # 중복 실행 방지
        if self._is_running_cycle:
            await update.message.reply_text(
                "⏳ 이미 트레이딩 사이클이 실행 중입니다.\n잠시 후 다시 시도해주세요."
            )
            return

        self._is_running_cycle = True

        try:
            await update.message.reply_text(
                "🚀 <b>트레이딩 사이클 시작</b>\n\n"
                "멀티코인 스캐닝 → 백테스팅 → AI 분석 → 거래 실행\n\n"
                "⏳ 처리 중... (약 1-3분 소요)",
                parse_mode="HTML"
            )

            start_time = datetime.now()

            # 트레이딩 사이클 실행
            from main import execute_trading_cycle
            from src.api.upbit_client import UpbitClient
            from src.data.collector import DataCollector
            from src.trading.service import TradingService
            from src.ai.service import AIService
            from src.config.settings import TradingConfig

            ticker = TradingConfig.TICKER
            upbit_client = UpbitClient()
            data_collector = DataCollector()
            trading_service = TradingService(upbit_client)
            ai_service = AIService()

            result = await execute_trading_cycle(
                ticker=ticker,
                upbit_client=upbit_client,
                data_collector=data_collector,
                trading_service=trading_service,
                ai_service=ai_service
            )

            duration = (datetime.now() - start_time).total_seconds()

            # 결과 메시지 생성
            if result.get('status') == 'success':
                decision = result.get('decision', 'unknown')
                decision_kr = {'buy': '매수', 'sell': '매도', 'hold': '관망'}.get(decision, decision)
                confidence = result.get('confidence', 'medium')
                reason = result.get('reason', '')[:200]

                if decision in ['buy', 'sell'] and result.get('trade_success'):
                    trade_emoji = "💰" if decision == 'buy' else "💸"
                    message = f"""
{trade_emoji} <b>거래 실행 완료</b>

📊 <b>결정:</b> {decision_kr.upper()}
📈 <b>신뢰도:</b> {confidence.upper()}
⏱️ <b>소요 시간:</b> {duration:.1f}초

💭 <b>AI 판단:</b>
{reason}
                    """
                else:
                    message = f"""
✅ <b>트레이딩 사이클 완료</b>

📊 <b>결정:</b> {decision_kr.upper()}
📈 <b>신뢰도:</b> {confidence.upper()}
⏱️ <b>소요 시간:</b> {duration:.1f}초

💭 <b>AI 판단:</b>
{reason}
                    """
            else:
                error_msg = result.get('error', '알 수 없는 오류')
                message = f"""
❌ <b>트레이딩 사이클 실패</b>

⏱️ <b>소요 시간:</b> {duration:.1f}초
⚠️ <b>오류:</b> {error_msg}
                """

            await update.message.reply_text(message, parse_mode="HTML")

        except Exception as e:
            logger.error(f"트레이딩 사이클 실행 중 오류: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ <b>오류 발생</b>\n\n{str(e)[:200]}",
                parse_mode="HTML"
            )
        finally:
            self._is_running_cycle = False

    async def _cmd_status(self, update, context):
        """봇 상태 확인"""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ 권한이 없습니다.")
            return

        try:
            from src.api.upbit_client import UpbitClient
            from src.position.portfolio_manager import PortfolioManager

            upbit_client = UpbitClient()
            pm = PortfolioManager(exchange_client=upbit_client)
            status = pm.get_portfolio_status()

            running_status = "🔴 중지됨" if not self._is_running_cycle else "🟢 실행 중"

            message = f"""
📊 <b>봇 상태</b>

━━━━━━━━━━━━━━━━━━━━
<b>🤖 시스템 상태</b>
━━━━━━━━━━━━━━━━━━━━
📌 <b>봇 상태:</b> {running_status}
💼 <b>트레이딩 모드:</b> {status.trading_mode.value.upper()}
📦 <b>보유 포지션:</b> {len(status.positions)}개
🔓 <b>신규 진입 가능:</b> {'예' if status.can_open_new_position else '아니오'}

━━━━━━━━━━━━━━━━━━━━
<b>💰 자산 현황</b>
━━━━━━━━━━━━━━━━━━━━
💵 <b>총 자산:</b> {status.total_value:,.0f} KRW
💴 <b>가용 현금:</b> {status.available_krw:,.0f} KRW
📈 <b>투자 금액:</b> {status.total_invested:,.0f} KRW

🕐 <b>확인 시각:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """

            await update.message.reply_text(message, parse_mode="HTML")

        except Exception as e:
            logger.error(f"상태 확인 중 오류: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ 상태 확인 실패: {str(e)[:100]}",
                parse_mode="HTML"
            )

    async def _cmd_positions(self, update, context):
        """보유 포지션 목록"""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ 권한이 없습니다.")
            return

        try:
            from src.api.upbit_client import UpbitClient
            from src.position.portfolio_manager import PortfolioManager
            from src.scanner.sector_mapping import get_coin_sector, get_sector_korean_name

            upbit_client = UpbitClient()
            pm = PortfolioManager(exchange_client=upbit_client)
            status = pm.get_portfolio_status()

            if not status.positions:
                await update.message.reply_text(
                    "📭 <b>보유 포지션 없음</b>\n\n현재 보유 중인 코인이 없습니다.",
                    parse_mode="HTML"
                )
                return

            message = "📦 <b>보유 포지션 목록</b>\n\n"

            for i, pos in enumerate(status.positions, 1):
                sector = get_coin_sector(pos.symbol)
                sector_name = get_sector_korean_name(sector)

                pnl_emoji = "📈" if pos.unrealized_pnl >= 0 else "📉"
                pnl_sign = "+" if pos.unrealized_pnl >= 0 else ""

                message += f"""
━━━━━━━━━━━━━━━━━━━━
<b>{i}. {pos.symbol}</b> [{sector_name}]
━━━━━━━━━━━━━━━━━━━━
💵 <b>평균 단가:</b> {pos.avg_buy_price:,.0f} KRW
💴 <b>현재가:</b> {pos.current_price:,.0f} KRW
📦 <b>수량:</b> {pos.balance:.8f}
💰 <b>평가금액:</b> {pos.current_value:,.0f} KRW
{pnl_emoji} <b>수익률:</b> {pnl_sign}{pos.profit_rate:.2f}%
"""

            message += f"\n🕐 <b>확인 시각:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            await update.message.reply_text(message, parse_mode="HTML")

        except Exception as e:
            logger.error(f"포지션 확인 중 오류: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ 포지션 확인 실패: {str(e)[:100]}",
                parse_mode="HTML"
            )

    async def _cmd_balance(self, update, context):
        """잔고 확인"""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ 권한이 없습니다.")
            return

        try:
            from src.api.upbit_client import UpbitClient

            upbit_client = UpbitClient()
            balances = upbit_client.get_balances()

            message = "💰 <b>잔고 현황</b>\n\n"

            total_krw = 0

            for bal in balances:
                currency = bal.get('currency', '')
                balance = float(bal.get('balance', 0))
                avg_buy_price = float(bal.get('avg_buy_price', 0))

                if balance <= 0:
                    continue

                if currency == 'KRW':
                    total_krw += balance
                    message += f"💵 <b>KRW:</b> {balance:,.0f}\n"
                else:
                    current_price = upbit_client.get_current_price(f"KRW-{currency}")
                    if current_price:
                        value = balance * current_price
                        total_krw += value
                        pnl = ((current_price - avg_buy_price) / avg_buy_price * 100) if avg_buy_price > 0 else 0
                        pnl_sign = "+" if pnl >= 0 else ""
                        message += f"🪙 <b>{currency}:</b> {balance:.8f} (≈{value:,.0f} KRW, {pnl_sign}{pnl:.2f}%)\n"

            message += f"\n━━━━━━━━━━━━━━━━━━━━\n"
            message += f"💎 <b>총 자산:</b> {total_krw:,.0f} KRW\n"
            message += f"\n🕐 <b>확인 시각:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            await update.message.reply_text(message, parse_mode="HTML")

        except Exception as e:
            logger.error(f"잔고 확인 중 오류: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ 잔고 확인 실패: {str(e)[:100]}",
                parse_mode="HTML"
            )


class GracefulKiller:
    """Graceful Shutdown 핸들러"""

    kill_now = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        self.kill_now = True


async def main():
    """메인 함수"""
    killer = GracefulKiller()
    bot_service = TelegramBotService()

    try:
        # 봇 시작
        await bot_service.start()

        # 종료 시그널 대기
        while not killer.kill_now:
            await asyncio.sleep(1)

        logger.info("\n시그널 수신: 봇 종료 중...")

    except Exception as e:
        logger.error(f"봇 실행 중 오류: {e}", exc_info=True)
    finally:
        await bot_service.stop()


def validate_environment_variables() -> bool:
    """필수 환경변수 검증"""
    required_vars = {
        'TELEGRAM_BOT_TOKEN': 'Telegram 봇 토큰',
        'UPBIT_ACCESS_KEY': 'Upbit API 액세스 키',
        'UPBIT_SECRET_KEY': 'Upbit API 시크릿 키',
    }

    missing_vars = []
    for var_name, description in required_vars.items():
        if not os.getenv(var_name):
            missing_vars.append(f"  - {var_name}: {description}")

    if missing_vars:
        logger.error("=" * 60)
        logger.error("❌ 필수 환경변수가 누락되었습니다")
        logger.error("=" * 60)
        for var in missing_vars:
            logger.error(var)
        logger.error("=" * 60)
        return False

    logger.info("✅ 필수 환경변수 검증 완료")
    return True


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🤖 Telegram 봇 명령어 서비스")
    print("=" * 60)
    print(f"시작 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"중지 방법: Ctrl + C")
    print("=" * 60 + "\n")

    if not validate_environment_variables():
        logger.error("❌ 환경변수 검증 실패로 프로그램을 종료합니다.")
        sys.exit(1)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n✅ Telegram 봇이 종료되었습니다.\n")
        sys.exit(0)
