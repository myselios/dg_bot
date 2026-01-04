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
from src.scanner.sector_mapping import get_coin_sector, get_sector_korean_name


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

    def _format_failed_filters(
        self,
        failed_filters: list,
        metrics: dict,
        filter_names: dict
    ) -> str:
        """
        실패한 필터를 실제값/기준값과 함께 포맷팅

        Args:
            failed_filters: 실패한 필터 키 리스트
            metrics: 백테스트 메트릭 딕셔너리
            filter_names: 필터 이름 한글화 딕셔너리

        Returns:
            포맷팅된 문자열 (예: "거래수(5/10), Sharpe(0.3/0.4)")
        """
        from src.backtesting.quick_filter import ResearchPassConfig

        # 기준값 (ResearchPassConfig 기준)
        config = ResearchPassConfig()
        thresholds = {
            'return': ('min', config.min_return, '%'),
            'win_rate': ('min', config.min_win_rate, '%'),
            'profit_factor': ('min', config.min_profit_factor, ''),
            'sharpe_ratio': ('min', config.min_sharpe_ratio, ''),
            'sortino_ratio': ('min', config.min_sortino_ratio, ''),
            'calmar_ratio': ('min', config.min_calmar_ratio, ''),
            'max_drawdown': ('max', config.max_drawdown, '%'),
            'max_consecutive_losses': ('max', config.max_consecutive_losses, ''),
            'volatility': ('max', config.max_volatility, '%'),
            'min_trades': ('min', config.min_trades, ''),
            'avg_win_loss_ratio': ('min', config.min_avg_win_loss_ratio, ''),
            'avg_holding_hours': ('max', config.max_avg_holding_hours, 'h'),
        }

        # 메트릭 키 매핑
        metric_keys = {
            'return': 'total_return',
            'win_rate': 'win_rate',
            'profit_factor': 'profit_factor',
            'sharpe_ratio': 'sharpe_ratio',
            'sortino_ratio': 'sortino_ratio',
            'calmar_ratio': 'calmar_ratio',
            'max_drawdown': 'max_drawdown',
            'max_consecutive_losses': 'max_consecutive_losses',
            'volatility': 'volatility',
            'min_trades': 'total_trades',
            'avg_win_loss_ratio': None,  # 계산 필요
            'avg_holding_hours': 'avg_holding_period_hours',
        }

        details = []
        for f in failed_filters:
            name = filter_names.get(f, f)
            threshold_info = thresholds.get(f)
            if not threshold_info:
                details.append(name)
                continue

            direction, threshold, unit = threshold_info
            metric_key = metric_keys.get(f)

            # 실제값 추출
            if f == 'avg_win_loss_ratio':
                avg_win = metrics.get('avg_win', 0)
                avg_loss = abs(metrics.get('avg_loss', 1))
                actual = avg_win / avg_loss if avg_loss > 0 else 0
            elif f == 'max_drawdown':
                actual = abs(metrics.get(metric_key, 0))
            elif metric_key:
                actual = metrics.get(metric_key, 0)
            else:
                details.append(name)
                continue

            # 포맷팅 (정수/소수 구분)
            if isinstance(actual, float) and not actual.is_integer():
                actual_str = f"{actual:.1f}"
            else:
                actual_str = str(int(actual)) if isinstance(actual, float) else str(actual)

            if isinstance(threshold, float) and not threshold.is_integer():
                threshold_str = f"{threshold:.1f}"
            else:
                threshold_str = str(int(threshold)) if isinstance(threshold, float) else str(threshold)

            op = '≥' if direction == 'min' else '≤'
            details.append(f"{name}({actual_str}{op}{threshold_str}{unit})")

        return ', '.join(details)

    def _format_scan_result(self, result: dict) -> str:
        """
        스캔 및 백테스트 결과를 포맷팅 (notify_scan_result 형식)

        스케줄러의 출력 형식과 동일하게:
        - 스캔 요약 (유동성, 백테스트, AI 분석, 최종선택)
        - 선택된 코인 정보 (섹터 포함)
        - 백테스팅 결과 상세 (코인별 필터 통과/실패)
        """
        lines = []

        # scan_summary 또는 scan_result에서 정보 추출
        scan_summary = result.get('scan_summary') or result.get('scan_result') or {}
        selected_coin = result.get('selected_coin')
        all_backtest_results = result.get('all_backtest_results') or result.get('backtest_results') or []

        # ━━━━━━━━━━━━━━━━━━━━━
        # 📊 스캔 요약
        # ━━━━━━━━━━━━━━━━━━━━━
        if scan_summary:
            liquidity_scanned = scan_summary.get('liquidity_scanned', 0)
            backtest_passed = scan_summary.get('backtest_passed', 0)
            ai_analyzed = scan_summary.get('ai_analyzed', 0)
            selected = scan_summary.get('selected', 0)
            duration = scan_summary.get('duration_seconds', 0)

            lines.append("🔍 <b>멀티코인 스캔 결과</b>")
            lines.append("")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("<b>📊 스캔 요약</b>")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append(f"📈 <b>유동성 스캔:</b> {liquidity_scanned}개 코인")
            lines.append(f"🔬 <b>백테스팅 통과:</b> {backtest_passed}개 코인")
            if ai_analyzed:
                lines.append(f"🤖 <b>AI 분석:</b> {ai_analyzed}개 코인")
            lines.append(f"✅ <b>최종 선택:</b> {selected}개 코인")
            if duration:
                lines.append(f"⏱️ <b>소요 시간:</b> {duration:.1f}초")

        # ━━━━━━━━━━━━━━━━━━━━━
        # 🎯 선택된 코인
        # ━━━━━━━━━━━━━━━━━━━━━
        if selected_coin:
            ticker = selected_coin.get('ticker', '')
            symbol = selected_coin.get('symbol', ticker.replace('KRW-', ''))
            score = selected_coin.get('score', 0)
            grade = selected_coin.get('grade', '')
            reason = selected_coin.get('reason', '')[:100] if selected_coin.get('reason') else ''

            # 섹터 정보
            sector = get_coin_sector(symbol)
            sector_name = get_sector_korean_name(sector)

            lines.append("")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("<b>🎯 선택된 코인</b>")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append(f"🪙 <b>심볼:</b> {symbol}")
            lines.append(f"🏷️ <b>섹터:</b> {sector_name}")
            lines.append(f"📊 <b>점수:</b> {score:.1f}점")
            if grade:
                lines.append(f"🏆 <b>등급:</b> {grade}")
            if reason:
                lines.append(f"📝 <b>선택 사유:</b> {reason}")

        # ━━━━━━━━━━━━━━━━━━━━━
        # 📋 백테스팅 결과 상세
        # ━━━━━━━━━━━━━━━━━━━━━
        if all_backtest_results and len(all_backtest_results) > 0:
            lines.append("")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("<b>📋 백테스팅 결과 상세</b>")
            lines.append("━━━━━━━━━━━━━━━━━━━━")

            # 필터 이름 한글화
            filter_names = {
                'return': '수익률',
                'win_rate': '승률',
                'profit_factor': '손익비',
                'sharpe_ratio': 'Sharpe',
                'sortino_ratio': 'Sortino',
                'calmar_ratio': 'Calmar',
                'max_drawdown': '낙폭',
                'max_consecutive_losses': '연속손실',
                'volatility': '변동성',
                'min_trades': '거래수',
                'avg_win_loss_ratio': '평균손익비',
                'avg_holding_hours': '보유시간',
                # Research Pass / Trading Pass 필터
                'expectancy': '기대값',
                'net_expectancy': '순기대값',
            }

            # 상위 5개만 표시 (섹터 정보 및 실패 조건 포함)
            for i, bt_result in enumerate(all_backtest_results[:5], 1):
                symbol = bt_result.get('symbol', 'N/A')
                if symbol == 'N/A':
                    # ticker에서 추출 시도
                    ticker = bt_result.get('ticker', '')
                    symbol = ticker.replace('KRW-', '') if ticker else 'N/A'

                sector = get_coin_sector(symbol)
                sector_name = get_sector_korean_name(sector)
                score = bt_result.get('score', 0)
                passed = bt_result.get('passed', False)
                passed_emoji = "✅" if passed else "❌"

                lines.append(f"\n<b>{i}. {passed_emoji} {symbol}</b> [{sector_name}] {score:.1f}점")

                # 필터 결과 상세 표시
                filter_results = bt_result.get('filter_results', {})
                if filter_results:
                    # 통과한 조건과 실패한 조건 분리
                    passed_filters = [k for k, v in filter_results.items() if v]
                    failed_filters = [k for k, v in filter_results.items() if not v]
                    total_filters = len(filter_results)

                    if passed:
                        lines.append(f"   ✅ 모든 조건 통과 ({len(passed_filters)}/{total_filters})")
                    else:
                        # 실패한 조건 표시 (실제값/기준값 포함)
                        metrics = bt_result.get('metrics', {})
                        failed_details = self._format_failed_filters(failed_filters, metrics, filter_names)
                        lines.append(f"   ❌ 실패: {failed_details}")
                        lines.append(f"   ✅ 통과: {len(passed_filters)}/{total_filters}")
                else:
                    # filter_results가 없을 경우 기본 정보 표시
                    research_pass = bt_result.get('research_pass', False)
                    trading_pass = bt_result.get('trading_pass', False)

                    if not passed:
                        fail_reasons = []
                        if not research_pass:
                            fail_reasons.append("Research")
                        if not trading_pass:
                            fail_reasons.append("Trading")
                        if fail_reasons:
                            lines.append(f"   ❌ 실패: {', '.join(fail_reasons)} Pass")

        if not lines:
            return "📊 <b>스캔 정보 없음</b>"

        return "\n".join(lines)

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

            # Clean Architecture: Container를 통한 트레이딩 사이클 실행
            from src.container import Container
            from src.api.upbit_client import UpbitClient
            from src.data.collector import DataCollector
            from src.config.settings import TradingConfig

            ticker = TradingConfig.TICKER
            upbit_client = UpbitClient()
            data_collector = DataCollector()

            # Container 초기화 (AIService, TradingService 불필요)
            container = Container.create_from_legacy(
                upbit_client=upbit_client,
                data_collector=data_collector
            )

            # TradingOrchestrator를 통한 거래 사이클 실행
            orchestrator = container.get_trading_orchestrator()
            result = await orchestrator.execute_trading_cycle(
                ticker=ticker,
                trading_type='spot',
                enable_scanning=True,
                max_positions=3
            )

            duration = (datetime.now() - start_time).total_seconds()

            # 스캔/백테스트 결과 추출
            scan_info = self._format_scan_result(result)

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

{scan_info}
━━━━━━━━━━━━━━━━━━━━
📊 <b>결정:</b> {decision_kr.upper()}
📈 <b>신뢰도:</b> {confidence.upper() if confidence else 'N/A'}
⏱️ <b>소요 시간:</b> {duration:.1f}초

💭 <b>AI 판단:</b>
{reason}
                    """
                else:
                    message = f"""
✅ <b>트레이딩 사이클 완료</b>

{scan_info}
━━━━━━━━━━━━━━━━━━━━
📊 <b>결정:</b> {decision_kr.upper()}
📈 <b>신뢰도:</b> {confidence.upper() if confidence else 'N/A'}
⏱️ <b>소요 시간:</b> {duration:.1f}초

💭 <b>AI 판단:</b>
{reason}
                    """
            else:
                error_msg = result.get('error', '알 수 없는 오류')
                message = f"""
❌ <b>트레이딩 사이클 실패</b>

{scan_info}
━━━━━━━━━━━━━━━━━━━━
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
💵 <b>총 자산:</b> {status.total_current_value:,.0f} KRW
💴 <b>가용 현금:</b> {status.krw_balance:,.0f} KRW
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
