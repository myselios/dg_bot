"""
알림 서비스
Telegram을 통한 실시간 알림을 전송합니다.
"""
import logging
import asyncio
import html
from typing import Optional
from datetime import datetime
from decimal import Decimal

from backend.app.core.config import settings
from src.scanner.sector_mapping import get_coin_sector, get_sector_korean_name

logger = logging.getLogger(__name__)


def escape_html(text: str) -> str:
    """
    HTML 특수 문자를 이스케이프 처리
    Telegram HTML parse_mode에서 사용 가능하도록 변환
    
    Args:
        text: 이스케이프할 텍스트
    
    Returns:
        str: 이스케이프된 텍스트
    """
    if not text:
        return ""
    
    # HTML 특수 문자 이스케이프
    text = html.escape(str(text))
    
    # Telegram HTML에서 허용되는 태그는 복원
    # 하지만 안전을 위해 기본적으로 모두 이스케이프된 상태 유지
    return text


class TelegramNotifier:
    """Telegram 봇을 통한 알림 전송"""
    
    def __init__(self):
        self.enabled = settings.TELEGRAM_ENABLED
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self._bot = None
        
        if self.enabled:
            try:
                from telegram import Bot
                self._bot = Bot(token=self.bot_token)
                logger.info("✅ Telegram 봇 초기화 완료")
            except ImportError:
                logger.error("python-telegram-bot 라이브러리가 설치되지 않았습니다.")
                self.enabled = False
            except Exception as e:
                logger.error(f"Telegram 봇 초기화 실패: {e}")
                self.enabled = False
    
    async def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        메시지 전송
        
        Args:
            message: 전송할 메시지
            parse_mode: 파싱 모드 (HTML, Markdown)
        
        Returns:
            bool: 전송 성공 여부
        """
        if not self.enabled or not self._bot:
            logger.debug(f"Telegram 알림 비활성화: {message}")
            return False
        
        try:
            await self._bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode,
            )
            logger.info("✅ Telegram 메시지 전송 성공")
            return True
        except Exception as e:
            logger.error(f"Telegram 메시지 전송 실패: {e}")
            return False

    def _get_filter_table_data(self, metrics: dict, filter_results: dict) -> list:
        """
        필터 테이블 데이터 생성 (Phase 7: 티어별 구조)

        Args:
            metrics: 백테스트 메트릭 딕셔너리
            filter_results: 필터별 통과 여부

        Returns:
            [(티어, 필터명, 기준, 결과, 통과여부, 가중치), ...] 형태의 리스트
        """
        from src.backtesting.quick_filter import BacktestConfig, FILTER_WEIGHTS

        config = BacktestConfig()

        # 티어별 필터 정의: (tier, key, 한글명, 방향, 기준값, 단위, 메트릭키, 가중치)
        # Tier 1: 핵심 AND (필수 통과)
        # Tier 2: 중요 가중치 (5.0점)
        # Tier 3: 권장 가중치 (2.0점)
        filter_defs = [
            # Tier 1: 핵심 AND (expectancy는 별도 계산)
            (1, 'return', '수익률', 'min', config.min_return, '%', 'total_return', 'AND'),
            (1, 'profit_factor', '손익비', 'min', config.min_profit_factor, '', 'profit_factor', 'AND'),
            (1, 'sharpe_ratio', 'Sharpe', 'min', config.min_sharpe_ratio, '', 'sharpe_ratio', 'AND'),
            # Tier 2: 중요 가중치 (5.0점)
            (2, 'max_drawdown', 'MDD', 'max', config.max_drawdown, '%', 'max_drawdown', 2.0),
            (2, 'sortino_ratio', 'Sortino', 'min', config.min_sortino_ratio, '', 'sortino_ratio', 1.5),
            (2, 'min_trades', '거래수', 'min', config.min_trades, '', 'total_trades', 1.0),
            (2, 'win_rate', '승률', 'min', config.min_win_rate, '%', 'win_rate', 0.5),
            # Tier 3: 권장 가중치 (2.0점)
            (3, 'calmar_ratio', 'Calmar', 'min', config.min_calmar_ratio, '', 'calmar_ratio', 1.0),
            (3, 'avg_win_loss_ratio', '평균손익', 'min', config.min_avg_win_loss_ratio, '', None, 0.5),
        ]

        rows = []
        # metrics가 빈 딕셔너리인지 확인 (빈 경우 실제값은 N/A로 표시)
        has_metrics = bool(metrics)

        for tier, key, name, direction, threshold, unit, metric_key, weight in filter_defs:
            # 실제값 추출 (metrics가 없으면 None)
            actual = None
            if has_metrics:
                if key == 'avg_win_loss_ratio':
                    avg_win = metrics.get('avg_win', 0)
                    avg_loss = abs(metrics.get('avg_loss', 1))
                    actual = avg_win / avg_loss if avg_loss > 0 else 0
                elif key == 'max_drawdown':
                    actual = abs(metrics.get(metric_key, 0)) if metric_key else 0
                elif metric_key:
                    actual = metrics.get(metric_key, 0)
                else:
                    actual = 0

            # 통과 여부
            passed = filter_results.get(key, False)

            # 기준값 포맷팅 (min 8% 또는 max 25% - HTML 태그 방지)
            op = 'min' if direction == 'min' else 'max'
            if isinstance(threshold, float) and not float(threshold).is_integer():
                threshold_str = f"{op}{threshold:.1f}{unit}"
            else:
                threshold_str = f"{op}{int(threshold)}{unit}"

            # 실제값 포맷팅 (None이면 N/A)
            if actual is None:
                actual_str = "N/A"
            elif isinstance(actual, float) and actual != 0:
                actual_str = f"{actual:.1f}{unit}"
            else:
                actual_str = f"{int(actual) if isinstance(actual, float) else actual}{unit}"

            # 티어 및 가중치 정보 포함
            rows.append((tier, name, threshold_str, actual_str, passed, weight))

        return rows

    def _get_display_width(self, text: str) -> int:
        """
        문자열의 표시 너비 계산 (한글=2, 영문/숫자=1)
        """
        width = 0
        for char in text:
            # 한글, 한자, 일본어 등은 2칸
            if '\uac00' <= char <= '\ud7af' or '\u4e00' <= char <= '\u9fff':
                width += 2
            else:
                width += 1
        return width

    def _pad_to_width(self, text: str, target_width: int) -> str:
        """
        문자열을 목표 너비에 맞게 패딩
        """
        current_width = self._get_display_width(text)
        padding = target_width - current_width
        return text + ' ' * max(0, padding)

    def _format_filter_table(self, rows: list) -> str:
        """
        필터 테이블을 텍스트로 포맷팅 (Phase 7: 티어별)

        Args:
            rows: [(티어, 필터명, 기준, 결과, 통과여부, 가중치), ...]

        Returns:
            고정폭 폰트용 테이블 문자열
        """
        lines = []

        # 티어별 그룹화
        tier_names = {1: "T1(AND)", 2: "T2(5.0)", 3: "T3(2.0)"}
        current_tier = 0

        for tier, name, threshold, actual, passed, weight in rows:
            # 티어 변경 시 헤더 추가
            if tier != current_tier:
                if current_tier != 0:
                    lines.append("")  # 티어 간 빈 줄
                tier_label = tier_names.get(tier, f"T{tier}")
                lines.append(f"[{tier_label}]")
                current_tier = tier

            pf = "✓" if passed else "✗"
            # 가중치 표시 (AND 또는 숫자)
            if weight == 'AND':
                weight_str = ""
            else:
                weight_str = f"({weight})"

            name_pad = self._pad_to_width(name, 6)
            threshold_pad = self._pad_to_width(threshold, 8)
            actual_pad = self._pad_to_width(actual, 8)
            lines.append(f"{name_pad}│{threshold_pad}│{actual_pad}│{pf}{weight_str}")

        return '\n'.join(lines)

    async def notify_trade(
        self,
        symbol: str,
        side: str,
        price: Decimal,
        amount: Decimal,
        total: Decimal,
        reason: Optional[str] = None,
    ) -> bool:
        """
        거래 실행 알림
        
        Args:
            symbol: 거래 심볼
            side: 매수/매도
            price: 체결 가격
            amount: 거래 수량
            total: 총 거래 금액
            reason: AI 판단 이유
        """
        emoji = "💰" if side == "buy" else "💸"
        side_kr = "매수" if side == "buy" else "매도"
        
        message = f"""
{emoji} <b>{side_kr} 거래 실행</b>

📊 <b>심볼:</b> {symbol}
💵 <b>가격:</b> {price:,.0f} KRW
📦 <b>수량:</b> {amount:.8f}
💰 <b>총액:</b> {total:,.0f} KRW

🕐 <b>시각:</b> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
        
        if reason:
            message += f"\n🤖 <b>AI 판단:</b> {reason}"
        
        return await self.send_message(message)
    
    async def notify_error(
        self,
        error_type: str,
        error_message: str,
        context: Optional[dict] = None,
    ) -> bool:
        """
        에러 발생 알림
        
        Args:
            error_type: 에러 타입
            error_message: 에러 메시지
            context: 추가 컨텍스트 정보
        """
        # HTML 특수 문자 이스케이프 (< > & 등)
        error_type_escaped = escape_html(error_type)
        error_message_escaped = escape_html(error_message)

        message = f"""
⚠️ <b>에러 발생</b>

🔴 <b>타입:</b> {error_type_escaped}
📝 <b>메시지:</b> {error_message_escaped}

🕐 <b>시각:</b> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
        
        if context:
            message += "\n<b>상세 정보:</b>\n"
            for key, value in context.items():
                message += f"  • {key}: {value}\n"
        
        return await self.send_message(message)
    
    async def notify_daily_report(
        self,
        total_trades: int,
        profit_loss: Decimal,
        profit_rate: Decimal,
        current_value: Decimal,
    ) -> bool:
        """
        일일 리포트 알림
        
        Args:
            total_trades: 총 거래 수
            profit_loss: 수익/손실 금액
            profit_rate: 수익률
            current_value: 현재 포트폴리오 가치
        """
        profit_emoji = "📈" if profit_loss >= 0 else "📉"
        profit_sign = "+" if profit_loss >= 0 else ""
        
        message = f"""
📊 <b>일일 트레이딩 리포트</b>

{profit_emoji} <b>수익률:</b> {profit_sign}{profit_rate:.2f}%
💰 <b>수익/손실:</b> {profit_sign}{profit_loss:,.0f} KRW
📦 <b>거래 횟수:</b> {total_trades}회
💵 <b>현재 자산:</b> {current_value:,.0f} KRW

📅 <b>날짜:</b> {datetime.now().strftime("%Y-%m-%d")}
"""
        
        return await self.send_message(message)
    
    async def notify_bot_status(self, status: str, message: str) -> bool:
        """
        봇 상태 변경 알림
        
        Args:
            status: 상태 (started, stopped, paused)
            message: 추가 메시지
        """
        emoji_map = {
            "started": "▶️",
            "stopped": "⏹️",
            "paused": "⏸️",
        }
        
        emoji = emoji_map.get(status, "ℹ️")
        
        notification = f"""
{emoji} <b>봇 상태 변경</b>

📌 <b>상태:</b> {status.upper()}
📝 <b>메시지:</b> {message}

🕐 <b>시각:</b> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
        
        return await self.send_message(notification)
    
    async def notify_trading_cycle_log(
        self,
        symbol: str,
        result: dict,
        duration: float,
        market_data: Optional[dict] = None,
    ) -> bool:
        """
        트레이딩 사이클 전체 로그 알림
        
        Args:
            symbol: 거래 심볼
            result: 트레이딩 사이클 실행 결과
            duration: 실행 소요 시간 (초)
            market_data: 시장 데이터 (현재가, 거래량 등)
        """
        # 성공/실패 이모지
        status_emoji = "✅" if result.get('status') == 'success' else "❌"
        
        # AI 판단 이모지
        decision = result.get('decision', 'unknown')
        decision_emoji_map = {
            'buy': '💰',
            'sell': '💸',
            'hold': '⏸️',
        }
        decision_emoji = decision_emoji_map.get(decision, '❓')
        decision_kr = {'buy': '매수', 'sell': '매도', 'hold': '관망'}.get(decision, decision)
        
        # 기본 메시지
        message = f"""
{status_emoji} <b>트레이딩 사이클 실행 로그</b>

━━━━━━━━━━━━━━━━━━━━
<b>📊 기본 정보</b>
━━━━━━━━━━━━━━━━━━━━
🪙 <b>심볼:</b> {symbol}
🕐 <b>시각:</b> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
⏱️ <b>소요 시간:</b> {duration:.2f}초

━━━━━━━━━━━━━━━━━━━━
<b>🤖 AI 판단 결과</b>
━━━━━━━━━━━━━━━━━━━━
{decision_emoji} <b>결정:</b> {decision_kr.upper()}
"""
        
        # 신뢰도 정보
        confidence = result.get('confidence', 'medium')
        confidence_map = {'high': 0.8, 'medium': 0.5, 'low': 0.3}
        confidence_value = confidence_map.get(confidence, 0.5)
        confidence_bar = "█" * int(confidence_value * 10) + "░" * (10 - int(confidence_value * 10))
        message += f"📈 <b>신뢰도:</b> {confidence.upper()} ({confidence_value * 100:.0f}%)\n"
        message += f"   {confidence_bar}\n"
        
        # AI 판단 이유 (HTML 이스케이프 처리)
        reason = result.get('reason', '분석 중')
        if len(reason) > 300:
            reason = reason[:297] + "..."
        # HTML 특수 문자 이스케이프 (< > & 등)
        reason_escaped = escape_html(reason)
        message += f"💭 <b>이유:</b>\n   {reason_escaped}\n"
        
        # 시장 데이터 (있는 경우)
        if market_data:
            message += f"\n━━━━━━━━━━━━━━━━━━━━\n"
            message += f"<b>📈 시장 데이터</b>\n"
            message += f"━━━━━━━━━━━━━━━━━━━━\n"
            
            if 'current_price' in market_data:
                message += f"💵 <b>현재가:</b> {market_data['current_price']:,.0f} KRW\n"
            
            if 'volume_24h' in market_data:
                message += f"📦 <b>24h 거래량:</b> {market_data['volume_24h']:,.2f}\n"
            
            if 'change_rate' in market_data:
                change_rate = market_data['change_rate']
                change_emoji = "📈" if change_rate >= 0 else "📉"
                change_sign = "+" if change_rate >= 0 else ""
                message += f"{change_emoji} <b>24h 변동률:</b> {change_sign}{change_rate:.2f}%\n"
            
            if 'rsi' in market_data:
                rsi = market_data['rsi']
                rsi_status = "과매수" if rsi > 70 else "과매도" if rsi < 30 else "중립"
                message += f"📊 <b>RSI(14):</b> {rsi:.2f} ({rsi_status})\n"
            
            if 'ma_20' in market_data:
                message += f"📉 <b>MA(20):</b> {market_data['ma_20']:,.0f} KRW\n"
            
            if 'ma_60' in market_data:
                message += f"📉 <b>MA(60):</b> {market_data['ma_60']:,.0f} KRW\n"
        
        # 거래 실행 정보 (매수/매도인 경우)
        if decision in ['buy', 'sell'] and result.get('trade_id'):
            message += f"\n━━━━━━━━━━━━━━━━━━━━\n"
            message += f"<b>💱 거래 실행 내역</b>\n"
            message += f"━━━━━━━━━━━━━━━━━━━━\n"
            
            trade_success = result.get('trade_success', False)
            trade_status_emoji = "✅" if trade_success else "❌"
            trade_status = "성공" if trade_success else "실패"
            message += f"{trade_status_emoji} <b>거래 상태:</b> {trade_status}\n"
            message += f"🆔 <b>거래 ID:</b> {result['trade_id']}\n"
            
            if 'price' in result:
                message += f"💵 <b>체결가:</b> {result['price']:,.0f} KRW\n"
            
            if 'amount' in result:
                message += f"📦 <b>수량:</b> {result['amount']:.8f}\n"
            
            if 'total' in result:
                message += f"💰 <b>총액:</b> {result['total']:,.0f} KRW\n"
            
            if 'fee' in result:
                message += f"💸 <b>수수료:</b> {result['fee']:,.0f} KRW\n"
        
        # 백테스팅 결과 (있는 경우)
        if 'backtest_result' in result:
            backtest = result['backtest_result']
            message += f"\n━━━━━━━━━━━━━━━━━━━━\n"
            message += f"<b>📊 백테스팅 참고</b>\n"
            message += f"━━━━━━━━━━━━━━━━━━━━\n"
            
            if 'win_rate' in backtest:
                message += f"🎯 <b>승률:</b> {backtest['win_rate']:.2f}%\n"
            
            if 'total_return' in backtest:
                return_emoji = "📈" if backtest['total_return'] >= 0 else "📉"
                message += f"{return_emoji} <b>누적 수익률:</b> {backtest['total_return']:.2f}%\n"
            
            if 'sharpe_ratio' in backtest:
                message += f"📐 <b>샤프 비율:</b> {backtest['sharpe_ratio']:.2f}\n"
        
        # 포트폴리오 상태 (있는 경우)
        if 'portfolio' in result:
            portfolio = result['portfolio']
            message += f"\n━━━━━━━━━━━━━━━━━━━━\n"
            message += f"<b>💼 포트폴리오 현황</b>\n"
            message += f"━━━━━━━━━━━━━━━━━━━━\n"
            
            if 'krw_balance' in portfolio:
                message += f"💵 <b>보유 KRW:</b> {portfolio['krw_balance']:,.0f} KRW\n"
            
            if 'crypto_balance' in portfolio:
                message += f"🪙 <b>보유 코인:</b> {portfolio['crypto_balance']:.8f}\n"
            
            if 'total_value' in portfolio:
                message += f"💰 <b>총 자산:</b> {portfolio['total_value']:,.0f} KRW\n"
            
            if 'total_profit' in portfolio:
                profit = portfolio['total_profit']
                profit_emoji = "📈" if profit >= 0 else "📉"
                profit_sign = "+" if profit >= 0 else ""
                message += f"{profit_emoji} <b>누적 손익:</b> {profit_sign}{profit:,.0f} KRW\n"
        
        # 에러 정보 (실패한 경우)
        if result.get('status') != 'success':
            error_msg = result.get('error', 'Unknown error')
            # HTML 특수 문자 이스케이프
            error_msg_escaped = escape_html(error_msg)
            message += f"\n━━━━━━━━━━━━━━━━━━━━\n"
            message += f"<b>⚠️ 에러 정보</b>\n"
            message += f"━━━━━━━━━━━━━━━━━━━━\n"
            message += f"❌ {error_msg_escaped}\n"
        
        message += f"\n━━━━━━━━━━━━━━━━━━━━"
        
        return await self.send_message(message)
    
    async def notify_backtest_and_signals(
        self,
        symbol: str,
        backtest_result: dict,
        market_data: dict,
        flash_crash: dict = None,
        rsi_divergence: dict = None,
    ) -> bool:
        """
        백테스팅 결과 및 신호 분석 알림
        
        Args:
            symbol: 거래 심볼
            backtest_result: 백테스팅 결과
            market_data: 시장 데이터
            flash_crash: 플래시 크래시 감지 결과
            rsi_divergence: RSI 다이버전스 결과
        """
        message = f"""
📊 <b>백테스팅 및 신호 분석</b>

━━━━━━━━━━━━━━━━━━━━
<b>🔙 백테스팅 결과</b>
━━━━━━━━━━━━━━━━━━━━
"""
        
        if backtest_result:
            # QuickBacktestResult 객체 또는 딕셔너리 처리
            try:
                # QuickBacktestResult 객체인 경우 metrics에서 데이터 추출
                metrics = None
                if hasattr(backtest_result, 'metrics'):
                    metrics = backtest_result.metrics
                elif isinstance(backtest_result, dict) and 'metrics' in backtest_result:
                    metrics = backtest_result['metrics']
                elif isinstance(backtest_result, dict):
                    # 이미 metrics 형태인 경우
                    metrics = backtest_result

                if metrics:
                    # 승률
                    if 'win_rate' in metrics:
                        message += f"🎯 <b>승률:</b> {metrics['win_rate']:.2f}%\n"

                    # 수익률
                    if 'total_return' in metrics:
                        return_emoji = "📈" if metrics['total_return'] >= 0 else "📉"
                        message += f"{return_emoji} <b>수익률:</b> {metrics['total_return']:.2f}%\n"

                    # 샤프 비율
                    if 'sharpe_ratio' in metrics:
                        message += f"📐 <b>샤프 비율:</b> {metrics['sharpe_ratio']:.2f}\n"

                    # 최대 낙폭
                    if 'max_drawdown' in metrics:
                        message += f"📉 <b>최대 낙폭:</b> {metrics['max_drawdown']:.2f}%\n"

                    # 손익비 (Profit Factor)
                    if 'profit_factor' in metrics:
                        message += f"💰 <b>손익비:</b> {metrics['profit_factor']:.2f}\n"

                    # 총 거래 수
                    if 'total_trades' in metrics:
                        message += f"📊 <b>총 거래:</b> {metrics['total_trades']}회\n"

                    # 필터링 통과 여부
                    if hasattr(backtest_result, 'passed'):
                        passed_emoji = "✅" if backtest_result.passed else "❌"
                        passed_text = "통과" if backtest_result.passed else "미통과"
                        message += f"{passed_emoji} <b>필터링:</b> {passed_text}\n"
                else:
                    message += "ℹ️ 백테스팅 metrics 데이터 없음\n"
            except Exception as e:
                logger.warning(f"백테스팅 결과 파싱 실패: {e}")
                message += f"ℹ️ 백테스팅 데이터 파싱 오류: {e}\n"
        else:
            message += "ℹ️ 백테스팅 데이터 없음\n"
        
        # 시장 데이터
        message += f"\n━━━━━━━━━━━━━━━━━━━━\n"
        message += f"<b>📈 시장 데이터</b>\n"
        message += f"━━━━━━━━━━━━━━━━━━━━\n"
        
        if market_data:
            if 'current_price' in market_data:
                message += f"💵 <b>현재가:</b> {market_data['current_price']:,.0f} KRW\n"
            
            if 'change_rate' in market_data:
                change_rate = market_data['change_rate']
                change_emoji = "📈" if change_rate >= 0 else "📉"
                change_sign = "+" if change_rate >= 0 else ""
                message += f"{change_emoji} <b>24h 변동률:</b> {change_sign}{change_rate:.2f}%\n"
            
            if 'rsi' in market_data:
                rsi = market_data['rsi']
                rsi_status = "과매수" if rsi > 70 else "과매도" if rsi < 30 else "중립"
                message += f"📊 <b>RSI(14):</b> {rsi:.2f} ({rsi_status})\n"
            
            if 'ma_20' in market_data:
                message += f"📉 <b>MA(20):</b> {market_data['ma_20']:,.0f} KRW\n"
            
            if 'ma_60' in market_data:
                message += f"📉 <b>MA(60):</b> {market_data['ma_60']:,.0f} KRW\n"
        
        # 플래시 크래시
        if flash_crash and flash_crash.get('detected'):
            message += f"\n⚠️ <b>플래시 크래시 감지!</b>\n"
            message += f"   {escape_html(flash_crash.get('description', ''))}\n"
        
        # RSI 다이버전스
        if rsi_divergence:
            divergence_type = rsi_divergence.get('type', 'none')
            if divergence_type != 'none':
                divergence_emoji = "🔻" if divergence_type == 'bearish_divergence' else "🔺"
                divergence_kr = "하락" if divergence_type == 'bearish_divergence' else "상승"
                message += f"\n{divergence_emoji} <b>RSI 다이버전스:</b> {divergence_kr} 다이버전스 감지\n"
                message += f"   신뢰도: {rsi_divergence.get('confidence', 'low').upper()}\n"
                message += f"   {escape_html(rsi_divergence.get('description', ''))}\n"
        
        return await self.send_message(message)
    
    async def notify_ai_decision(
        self,
        symbol: str,
        decision: str,
        confidence: str,
        reason: str,
        duration: float,
        signal_analysis: dict = None,  # Phase 1: SignalAnalyzer 결과 추가
    ) -> bool:
        """
        AI 의사결정 상세 알림 (전체 텍스트, 분할 전송)

        Args:
            symbol: 거래 심볼
            decision: 결정 (buy/sell/hold)
            confidence: 신뢰도
            reason: AI 판단 이유 (전체)
            duration: 소요 시간
            signal_analysis: SignalAnalyzer 결과 (선택적)
        """
        decision_emoji_map = {
            'buy': '💰',
            'sell': '💸',
            'hold': '⏸️',
        }
        decision_emoji = decision_emoji_map.get(decision, '❓')
        decision_kr = {'buy': '매수', 'sell': '매도', 'hold': '관망'}.get(decision, decision)

        confidence_map = {'high': 0.8, 'medium': 0.5, 'low': 0.3, 'very_low': 0.1}
        confidence_value = confidence_map.get(confidence, 0.5)
        confidence_bar = "█" * int(confidence_value * 10) + "░" * (10 - int(confidence_value * 10))

        # entry_mode 판단: AI reason이 "Signal:"로 시작하면 신호 기반 진입
        is_signal_based = reason.startswith("Signal:")
        title = "📊 신호 기반 의사결정" if is_signal_based else "🤖 AI 의사결정 상세"

        # 메시지 헤더
        message = f"""
{title}

━━━━━━━━━━━━━━━━━━━━
<b>📋 결정 정보</b>
━━━━━━━━━━━━━━━━━━━━
{decision_emoji} <b>결정:</b> {decision_kr.upper()}
📈 <b>신뢰도:</b> {confidence.upper()} ({confidence_value * 100:.0f}%)
   {confidence_bar}
⏱️ <b>분석 소요 시간:</b> {duration:.2f}초
"""

        # SignalAnalyzer 결과 추가
        if signal_analysis:
            raw_decision = signal_analysis.get('decision', '')
            total_score = signal_analysis.get('total_score', 0)
            buy_score = signal_analysis.get('buy_score', 0)
            sell_score = signal_analysis.get('sell_score', 0)
            signals = signal_analysis.get('signals', [])[:5]  # 상위 5개만

            message += f"""
━━━━━━━━━━━━━━━━━━━━
<b>📈 신호 분석 결과</b>
━━━━━━━━━━━━━━━━━━━━
🎯 <b>원본 결정:</b> {raw_decision}
📊 <b>총 점수:</b> {total_score:.1f} (매수: {buy_score:.1f} / 매도: {sell_score:.1f})
"""
            if signals:
                message += "\n<b>주요 신호:</b>\n"
                for sig in signals:
                    message += f"  • {escape_html(sig)}\n"

        message += f"""
━━━━━━━━━━━━━━━━━━━━
<b>💭 {'신호 기반 판단' if is_signal_based else 'AI 판단 근거'}</b>
━━━━━━━━━━━━━━━━━━━━
"""
        
        # AI 이유는 HTML 이스케이프 후 전체 전송
        reason_escaped = escape_html(reason)
        
        # 텔레그램 메시지 길이 제한: 4096자
        # 헤더 + 이유가 4096자를 넘으면 분할 전송
        max_length = 4000  # 여유분 남기기
        
        if len(message) + len(reason_escaped) <= max_length:
            # 한 번에 전송
            message += reason_escaped
            return await self.send_message(message)
        else:
            # 분할 전송
            # 1) 헤더 전송
            success = await self.send_message(message)
            if not success:
                return False
            
            # 2) 이유 분할 전송
            reason_parts = []
            current_part = ""
            lines = reason_escaped.split('\n')
            
            for line in lines:
                if len(current_part) + len(line) + 1 <= max_length:
                    current_part += line + "\n"
                else:
                    if current_part:
                        reason_parts.append(current_part)
                    current_part = line + "\n"
            
            if current_part:
                reason_parts.append(current_part)
            
            # 각 부분 전송
            for i, part in enumerate(reason_parts, 1):
                part_message = f"<b>[계속 {i}/{len(reason_parts)}]</b>\n\n{part}"
                success = await self.send_message(part_message)
                if not success:
                    return False
            
            return True
    
    async def notify_scan_result(
        self,
        scan_summary: dict,
        selected_coin: dict = None,
        all_backtest_results: list = None,
    ) -> bool:
        """
        멀티코인 스캔 결과 알림

        Args:
            scan_summary: 스캔 요약 정보
            selected_coin: 선택된 코인 정보 (없으면 None)
            all_backtest_results: 모든 백테스팅 결과 (상위 N개)
        """
        message = f"""
🔍 <b>멀티코인 스캔 결과</b>

━━━━━━━━━━━━━━━━━━━━
<b>📊 스캔 요약</b>
━━━━━━━━━━━━━━━━━━━━
📈 <b>유동성 스캔:</b> {scan_summary.get('liquidity_scanned', 0)}개 코인
🔬 <b>백테스팅 통과:</b> {scan_summary.get('backtest_passed', 0)}개 코인
✅ <b>최종 선택:</b> {scan_summary.get('selected', 0)}개 코인
⏱️ <b>소요 시간:</b> {scan_summary.get('duration_seconds', 0):.1f}초
"""

        # 선택된 코인 정보
        if selected_coin:
            symbol = selected_coin.get('symbol', 'N/A')
            sector = get_coin_sector(symbol)
            sector_name = get_sector_korean_name(sector)
            message += f"""
━━━━━━━━━━━━━━━━━━━━
<b>🎯 선택된 코인</b>
━━━━━━━━━━━━━━━━━━━━
🪙 <b>심볼:</b> {symbol}
🏷️ <b>섹터:</b> {sector_name}
📊 <b>점수:</b> {selected_coin.get('score', 0):.1f}점
🏆 <b>등급:</b> {selected_coin.get('grade', 'N/A')}
📝 <b>선택 사유:</b> {escape_html(selected_coin.get('reason', '')[:100])}
"""

        # 백테스팅 상위 결과 (있는 경우) - 코인별 표 형식 표시
        if all_backtest_results and len(all_backtest_results) > 0:
            message += f"""
━━━━━━━━━━━━━━━━━━━━
<b>📋 스캔 결과 상세</b>
━━━━━━━━━━━━━━━━━━━━
"""
            # 상위 5개만 표시 (섹터 정보 및 필터 테이블 포함)
            for i, bt_result in enumerate(all_backtest_results[:5], 1):
                symbol = bt_result.get('symbol', 'N/A')
                sector = get_coin_sector(symbol)
                sector_name = get_sector_korean_name(sector)
                score = bt_result.get('score', 0)
                passed = bt_result.get('passed', False)
                bt_emoji = "✅" if passed else "❌"

                # 기대값 및 실제값 (백테스팅 결과에 포함)
                expectancy = bt_result.get('expectancy', None)
                metrics = bt_result.get('metrics', {})
                total_return = metrics.get('total_return', None)

                # 헤더: 코인명 + 섹터 + 점수
                message += f"\n<b>{i}. {symbol}</b> [{sector_name}] {score:.1f}점\n"

                # 백테스팅 상태 표시 (단일 게이트)
                if expectancy is not None or total_return is not None:
                    exp_str = f"{expectancy:.2f}R" if expectancy is not None else "N/A"
                    ret_str = f"{total_return:.2f}%" if total_return is not None else "N/A"
                    message += f"   📊 백테스트: {bt_emoji} (기대값: {exp_str}, 실제값: {ret_str})\n"
                else:
                    message += f"   📊 백테스트: {bt_emoji}\n"

                # 필터 결과 상세 표시 (표 형식)
                filter_results = bt_result.get('filter_results', {})

                # filter_results가 있으면 테이블 표시 (metrics 없어도 통과/실패 표시 가능)
                if filter_results:
                    # metrics가 없으면 빈 딕셔너리 사용 (실제값 0으로 표시)
                    rows = self._get_filter_table_data(metrics or {}, filter_results)
                    table = self._format_filter_table(rows)
                    message += f"<pre>{table}</pre>\n"
                else:
                    passed_count = 0
                    total_count = 12
                    message += f"   통과: {passed_count}/{total_count}\n"

        message += f"\n🕐 <b>시각:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        return await self.send_message(message)

    async def notify_portfolio_status(
        self,
        symbol: str,
        portfolio_data: dict,
        trade_result: dict = None,
    ) -> bool:
        """
        포트폴리오 현황 알림
        
        Args:
            symbol: 거래 심볼
            portfolio_data: 포트폴리오 데이터
            trade_result: 거래 결과 (있는 경우)
        """
        message = f"""
💼 <b>포트폴리오 현황</b>

━━━━━━━━━━━━━━━━━━━━
<b>💰 자산 상태</b>
━━━━━━━━━━━━━━━━━━━━
"""
        
        if portfolio_data:
            if 'krw_balance' in portfolio_data:
                message += f"💵 <b>보유 KRW:</b> {portfolio_data['krw_balance']:,.0f} KRW\n"
            
            if 'crypto_balance' in portfolio_data:
                message += f"🪙 <b>보유 코인:</b> {portfolio_data['crypto_balance']:.8f}\n"
            
            if 'total_value' in portfolio_data:
                message += f"💰 <b>총 자산:</b> {portfolio_data['total_value']:,.0f} KRW\n"
            
            if 'total_profit' in portfolio_data:
                profit = portfolio_data['total_profit']
                profit_emoji = "📈" if profit >= 0 else "📉"
                profit_sign = "+" if profit >= 0 else ""
                message += f"{profit_emoji} <b>누적 손익:</b> {profit_sign}{profit:,.0f} KRW\n"
        
        # 거래 실행 내역 (있는 경우)
        if trade_result:
            message += f"\n━━━━━━━━━━━━━━━━━━━━\n"
            message += f"<b>💱 거래 실행 내역</b>\n"
            message += f"━━━━━━━━━━━━━━━━━━━━\n"
            
            trade_success = trade_result.get('trade_success', False)
            trade_status_emoji = "✅" if trade_success else "❌"
            trade_status = "성공" if trade_success else "실패"
            message += f"{trade_status_emoji} <b>거래 상태:</b> {trade_status}\n"
            
            if 'trade_id' in trade_result:
                message += f"🆔 <b>거래 ID:</b> {trade_result['trade_id']}\n"
            
            if 'price' in trade_result:
                message += f"💵 <b>체결가:</b> {trade_result['price']:,.0f} KRW\n"
            
            if 'amount' in trade_result:
                message += f"📦 <b>수량:</b> {trade_result['amount']:.8f}\n"
            
            if 'total' in trade_result:
                message += f"💰 <b>총액:</b> {trade_result['total']:,.0f} KRW\n"
            
            if 'fee' in trade_result:
                message += f"💸 <b>수수료:</b> {trade_result['fee']:,.0f} KRW\n"
        
        message += f"\n🕐 <b>시각:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return await self.send_message(message)


# 전역 인스턴스
notifier = TelegramNotifier()


# 편의 함수들
async def notify_trade(*args, **kwargs) -> bool:
    """거래 알림 (전역 함수)"""
    return await notifier.notify_trade(*args, **kwargs)


async def notify_error(*args, **kwargs) -> bool:
    """에러 알림 (전역 함수)"""
    return await notifier.notify_error(*args, **kwargs)


async def notify_daily_report(*args, **kwargs) -> bool:
    """일일 리포트 알림 (전역 함수)"""
    return await notifier.notify_daily_report(*args, **kwargs)


async def notify_bot_status(*args, **kwargs) -> bool:
    """봇 상태 알림 (전역 함수)"""
    return await notifier.notify_bot_status(*args, **kwargs)


async def send_telegram_message(message: str, parse_mode: str = "HTML") -> bool:
    """텔레그램 메시지 직접 전송 (전역 함수)"""
    return await notifier.send_message(message, parse_mode)


async def notify_trading_cycle_log(*args, **kwargs) -> bool:
    """트레이딩 사이클 전체 로그 알림 (전역 함수)"""
    return await notifier.notify_trading_cycle_log(*args, **kwargs)


async def notify_cycle_start(
    symbol: str,
    status: str,
    message: str = "트레이딩 사이클을 시작합니다"
) -> bool:
    """트레이딩 사이클 시작 알림 (전역 함수)"""
    return await notifier.notify_bot_status(status, f"{symbol} - {message}")


async def notify_backtest_and_signals(
    symbol: str,
    backtest_result: dict,
    market_data: dict,
    flash_crash: dict = None,
    rsi_divergence: dict = None,
) -> bool:
    """백테스팅 결과 및 신호 분석 알림 (전역 함수)"""
    return await notifier.notify_backtest_and_signals(
        symbol, backtest_result, market_data, flash_crash, rsi_divergence
    )


async def notify_ai_decision(
    symbol: str,
    decision: str,
    confidence: str,
    reason: str,
    duration: float,
    signal_analysis: dict = None,  # Phase 1: SignalAnalyzer 결과 추가
) -> bool:
    """AI 의사결정 상세 알림 (전역 함수)"""
    return await notifier.notify_ai_decision(
        symbol, decision, confidence, reason, duration, signal_analysis
    )


async def notify_portfolio_status(
    symbol: str,
    portfolio_data: dict,
    trade_result: dict = None,
) -> bool:
    """포트폴리오 현황 알림 (전역 함수)"""
    return await notifier.notify_portfolio_status(
        symbol, portfolio_data, trade_result
    )


async def notify_scan_result(
    scan_summary: dict,
    selected_coin: dict = None,
    all_backtest_results: list = None,
) -> bool:
    """멀티코인 스캔 결과 알림 (전역 함수)"""
    return await notifier.notify_scan_result(
        scan_summary, selected_coin, all_backtest_results
    )


async def notify_position_status(
    positions: list,
    total_invested: float = 0,
    total_value: float = 0,
    krw_balance: float = 0,
) -> bool:
    """
    포지션 상태 알림 (15분 주기)

    Args:
        positions: 보유 포지션 리스트 [{'symbol': 'DOGE', 'invested': 95689, 'value': 92128, 'pnl': -3.72}, ...]
        total_invested: 총 투자 금액
        total_value: 총 평가 금액
        krw_balance: KRW 잔고
    """
    total_pnl = ((total_value - total_invested) / total_invested * 100) if total_invested > 0 else 0
    pnl_emoji = "📈" if total_pnl >= 0 else "📉"
    pnl_sign = "+" if total_pnl >= 0 else ""

    message = f"""
🔍 <b>포지션 관리 - 현황 체크</b>

━━━━━━━━━━━━━━━━━━━━
<b>💼 전체 포트폴리오</b>
━━━━━━━━━━━━━━━━━━━━
💵 <b>KRW 잔고:</b> {krw_balance:,.0f} KRW
📊 <b>보유 포지션:</b> {len(positions)}개
💰 <b>투자 금액:</b> {total_invested:,.0f} KRW
📈 <b>평가 금액:</b> {total_value:,.0f} KRW
{pnl_emoji} <b>총 손익:</b> {pnl_sign}{total_pnl:.2f}% ({pnl_sign}{total_value - total_invested:,.0f} KRW)
"""

    if positions:
        message += f"""
━━━━━━━━━━━━━━━━━━━━
<b>📋 개별 포지션 상태</b>
━━━━━━━━━━━━━━━━━━━━
"""
        for pos in positions:
            symbol = pos.get('symbol', 'N/A')
            invested = pos.get('invested', 0)
            value = pos.get('value', 0)
            pnl = pos.get('pnl', 0)

            # 투자 금액이 0인 항목은 제외
            if invested == 0:
                continue

            pos_emoji = "📈" if pnl >= 0 else "📉"
            pos_sign = "+" if pnl >= 0 else ""

            # 손절/익절 근접 상태 표시
            status = ""
            if pnl <= -5.0:
                status = " ⚠️ 손절 위험"
            elif pnl <= -4.0:
                status = " 🟡 손절 근접"
            elif pnl >= 10.0:
                status = " ✅ 익절 도달"
            elif pnl >= 8.0:
                status = " 🟢 익절 근접"

            message += f"""
🪙 <b>{symbol}</b>{status}
   투자: {invested:,.0f} → 평가: {value:,.0f}
   {pos_emoji} 손익: {pos_sign}{pnl:.2f}%
"""

    message += f"\n🕐 <b>시각:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    return await notifier.send_message(message)


async def notify_position_exit(
    symbol: str,
    exit_type: str,
    invested: float,
    exit_value: float,
    pnl: float,
    reason: str,
) -> bool:
    """
    포지션 청산 알림 (손절/익절)

    Args:
        symbol: 코인 심볼
        exit_type: 'stop_loss' 또는 'take_profit'
        invested: 투자 금액
        exit_value: 청산 금액
        pnl: 손익률 (%)
        reason: 청산 사유
    """
    if exit_type == 'stop_loss':
        emoji = "🔴"
        title = "손절 실행"
        color_emoji = "📉"
    elif exit_type == 'take_profit':
        emoji = "💚"
        title = "익절 실행"
        color_emoji = "📈"
    else:
        emoji = "💸"
        title = "포지션 청산"
        color_emoji = "📊"

    pnl_sign = "+" if pnl >= 0 else ""
    pnl_amount = exit_value - invested

    message = f"""
{emoji} <b>{title}</b>

━━━━━━━━━━━━━━━━━━━━
<b>💱 청산 정보</b>
━━━━━━━━━━━━━━━━━━━━
🪙 <b>심볼:</b> {symbol}
📝 <b>사유:</b> {escape_html(reason)}

💰 <b>투자 금액:</b> {invested:,.0f} KRW
💸 <b>청산 금액:</b> {exit_value:,.0f} KRW
{color_emoji} <b>실현 손익:</b> {pnl_sign}{pnl:.2f}% ({pnl_sign}{pnl_amount:,.0f} KRW)

🕐 <b>시각:</b> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

    return await notifier.send_message(message)


async def notify_trading_cycle_complete(
    decision: str,
    reason: str,
    positions: list,
    krw_balance: float = 0,
    total_invested: float = 0,
    total_value: float = 0,
    trading_mode: str = "entry",
    can_open_new_position: bool = True,
    max_positions: int = 3,
    duration: float = 0,
    trade_result: dict = None,
) -> bool:
    """
    트레이딩 사이클 완료 통합 알림

    로그와 동일한 형태로 한눈에 볼 수 있는 정보 제공

    Args:
        decision: AI 결정 (buy/sell/hold)
        reason: 결정 사유
        positions: 보유 포지션 리스트
        krw_balance: KRW 잔고
        total_invested: 총 투자 금액
        total_value: 총 평가 금액
        trading_mode: 거래 모드 (entry/management/blocked)
        can_open_new_position: 신규 진입 가능 여부
        max_positions: 최대 포지션 수
        duration: 소요 시간
        trade_result: 거래 실행 결과 (매수/매도 시)
    """
    # 결정 이모지
    decision_emoji_map = {
        'buy': '💰',
        'sell': '💸',
        'hold': '⏸️',
    }
    decision_emoji = decision_emoji_map.get(decision, '❓')
    decision_kr = {'buy': '매수', 'sell': '매도', 'hold': '관망'}.get(decision, decision)

    # 거래 모드 한글
    mode_kr = {'entry': '진입', 'management': '관리', 'blocked': '차단'}.get(trading_mode, trading_mode)

    # 진입 가능 여부
    can_entry_text = "Yes ✅" if can_open_new_position else "No ❌"

    # 총 손익 계산
    total_pnl = ((total_value - total_invested) / total_invested * 100) if total_invested > 0 else 0
    pnl_emoji = "📈" if total_pnl >= 0 else "📉"
    pnl_sign = "+" if total_pnl >= 0 else ""

    # 실제 포지션 수 (투자금액 > 0인 것만)
    valid_positions = [p for p in positions if p.get('invested', 0) > 0]
    position_count = len(valid_positions)

    message = f"""
✅ <b>트레이딩 사이클 완료</b>

━━━━━━━━━━━━━━━━━━━━
<b>📊 포트폴리오 현황</b>
━━━━━━━━━━━━━━━━━━━━
🔄 <b>거래 모드:</b> {mode_kr}
📦 <b>보유 포지션:</b> {position_count}/{max_positions}개
🚀 <b>신규 진입:</b> {can_entry_text}

💵 <b>현금 잔고:</b> {krw_balance:,.0f} KRW
💰 <b>투자 금액:</b> {total_invested:,.0f} KRW
📈 <b>평가 금액:</b> {total_value:,.0f} KRW
{pnl_emoji} <b>총 손익:</b> {pnl_sign}{total_pnl:.2f}% ({pnl_sign}{total_value - total_invested:,.0f} KRW)
"""

    # 개별 포지션 상태
    if valid_positions:
        message += """
━━━━━━━━━━━━━━━━━━━━
<b>📋 보유 포지션</b>
━━━━━━━━━━━━━━━━━━━━
"""
        for pos in valid_positions:
            symbol = pos.get('symbol', 'N/A')
            invested = pos.get('invested', 0)
            value = pos.get('value', 0)
            pnl = pos.get('pnl', 0)

            pos_emoji = "📈" if pnl >= 0 else "📉"
            pos_sign = "+" if pnl >= 0 else ""

            # 손절/익절 근접 상태 표시
            status = ""
            if pnl <= -5.0:
                status = " ⚠️ 손절"
            elif pnl <= -4.0:
                status = " 🟡 주의"
            elif pnl >= 10.0:
                status = " ✅ 익절"
            elif pnl >= 8.0:
                status = " 🟢 양호"

            message += f"  🪙 <b>{symbol}</b>{status}: {value:,.0f} KRW ({pos_sign}{pnl:.2f}%)\n"

    # 결정 정보
    message += f"""
━━━━━━━━━━━━━━━━━━━━
<b>🤖 AI 결정</b>
━━━━━━━━━━━━━━━━━━━━
{decision_emoji} <b>결정:</b> {decision_kr.upper()}
⏱️ <b>소요 시간:</b> {duration:.1f}초
💭 <b>사유:</b> {escape_html(reason[:200])}{"..." if len(reason) > 200 else ""}
"""

    # 거래 실행 결과 (매수/매도 성공 시)
    if trade_result and trade_result.get('trade_success'):
        trade_side = "매수" if decision == 'buy' else "매도"
        message += f"""
━━━━━━━━━━━━━━━━━━━━
<b>💱 거래 실행</b>
━━━━━━━━━━━━━━━━━━━━
✅ <b>{trade_side} 성공</b>
💵 체결가: {trade_result.get('price', 0):,.0f} KRW
📦 수량: {trade_result.get('amount', 0):.8f}
💰 총액: {trade_result.get('total', 0):,.0f} KRW
"""

    message += f"\n🕐 <b>시각:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    return await notifier.send_message(message)
