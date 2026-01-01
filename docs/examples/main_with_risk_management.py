"""
리스크 관리가 통합된 main.py 예제

실전 투자에 필수적인 리스크 관리 로직을 main.py에 통합한 예시입니다.
이 파일은 예제이므로 실제 main.py를 교체하지 마세요.
"""
import asyncio
from typing import Dict, Optional, Any
from src.config.settings import TradingConfig
from src.api.upbit_client import UpbitClient
from src.data.collector import DataCollector
from src.trading.service import TradingService
from src.ai.service import AIService
from src.risk.manager import RiskManager, RiskLimits  # ← 새로 추가
from src.ai.validator import AIDecisionValidator  # ← 새로 추가
from src.utils.logger import Logger


async def execute_trading_cycle_with_risk_management(
    ticker: str,
    upbit_client: UpbitClient,
    data_collector: DataCollector,
    trading_service: TradingService,
    ai_service: AIService
) -> Dict[str, Any]:
    """
    리스크 관리가 통합된 거래 사이클

    실행 순서:
    1. 리스크 체크 (최우선) ← NEW
       - 손절/익절 체크
       - Circuit Breaker
       - 거래 빈도 제한
    2. 기술적 분석
    3. AI 분석
    4. AI 판단 검증 ← NEW
    5. 거래 실행
    """
    try:
        # ============================================
        # Step 0: 리스크 관리자 초기화
        # ============================================
        risk_manager = RiskManager(
            limits=RiskLimits(
                stop_loss_pct=-5.0,  # 손절: -5%
                take_profit_pct=10.0,  # 익절: +10%
                daily_loss_limit_pct=-10.0,  # 일일 최대 손실: -10%
                min_trade_interval_hours=4,  # 최소 거래 간격: 4시간
            )
        )

        # ============================================
        # Step 1: 리스크 체크 (최우선)
        # ============================================
        Logger.print_header("🛡️ 리스크 관리 체크")

        # 1.1 포지션 손익 체크 (손절/익절)
        position_info = PositionService(upbit_client).get_detailed_position(ticker)
        current_price = upbit_client.get_current_price(ticker)

        position_check = risk_manager.check_position_limits(position_info, current_price)

        if position_check['action'] == 'stop_loss':
            Logger.print_error(f"🚨 손절 발동: {position_check['reason']}")
            # 즉시 매도
            sell_result = trading_service.execute_sell(ticker)
            # 손익 기록
            risk_manager.record_trade(position_check['pnl_pct'])
            return {
                'status': 'success',
                'decision': 'sell',
                'reason': position_check['reason'],
                'trigger': 'stop_loss',
                'trade_result': sell_result
            }

        elif position_check['action'] == 'take_profit':
            Logger.print_success(f"💰 익절 발동: {position_check['reason']}")
            # 즉시 매도
            sell_result = trading_service.execute_sell(ticker)
            # 손익 기록
            risk_manager.record_trade(position_check['pnl_pct'])
            return {
                'status': 'success',
                'decision': 'sell',
                'reason': position_check['reason'],
                'trigger': 'take_profit',
                'trade_result': sell_result
            }

        # 1.2 Circuit Breaker 체크
        circuit_check = risk_manager.check_circuit_breaker()
        if not circuit_check['allowed']:
            Logger.print_error(f"⛔ Circuit Breaker 발동: {circuit_check['reason']}")
            return {
                'status': 'blocked',
                'decision': 'hold',
                'reason': circuit_check['reason'],
                'daily_pnl': circuit_check['daily_pnl'],
                'weekly_pnl': circuit_check['weekly_pnl']
            }

        # 1.3 거래 빈도 제한 체크
        frequency_check = risk_manager.check_trade_frequency()
        if not frequency_check['allowed']:
            Logger.print_warning(f"⏭️ 거래 스킵: {frequency_check['reason']}")
            return {
                'status': 'skipped',
                'decision': 'hold',
                'reason': frequency_check['reason'],
                'hours_since_last_trade': frequency_check['hours_since_last_trade']
            }

        Logger.print_success("✅ 모든 리스크 체크 통과 - 거래 진행")

        # ============================================
        # Step 2: 기술적 분석 (기존 로직)
        # ============================================
        Logger.print_header("📊 기술적 분석")

        # 차트 데이터 수집
        chart_data_with_btc = data_collector.get_chart_data_with_btc(ticker)
        if not chart_data_with_btc:
            return {'status': 'failed', 'reason': '차트 데이터 조회 실패'}

        chart_data = chart_data_with_btc['eth']
        btc_chart_data = chart_data_with_btc['btc']

        # 기술적 지표 계산
        from src.trading.indicators import TechnicalIndicators
        technical_indicators = TechnicalIndicators.get_latest_indicators(chart_data['day'])

        # 오더북 정보
        orderbook = data_collector.get_orderbook(ticker)
        orderbook_summary = data_collector.get_orderbook_summary(orderbook)

        # ============================================
        # Step 3: AI 분석 (기존 로직)
        # ============================================
        Logger.print_header("🤖 AI 분석")

        # AI 분석 데이터 준비
        current_status = {
            "krw_balance": upbit_client.get_balance("KRW"),
            "coin_balance": upbit_client.get_balance(ticker),
            "current_price": current_price
        }

        analysis_data = ai_service.prepare_analysis_data(
            chart_data,
            orderbook_summary,
            current_status,
            technical_indicators,
            position_info,
            None,  # fear_greed_index
            None,  # backtest_result
            None,  # market_correlation
            None,  # flash_crash
            None   # rsi_divergence
        )

        # AI 분석 수행
        ai_result = ai_service.analyze(ticker, analysis_data)

        if not ai_result:
            return {'status': 'failed', 'reason': 'AI 분석 실패'}

        Logger.print_decision(
            ai_result["decision"],
            ai_result["confidence"],
            ai_result["reason"]
        )

        # ============================================
        # Step 4: AI 판단 검증 (NEW)
        # ============================================
        Logger.print_header("🔍 AI 판단 검증")

        # 시장 환경 정보 수집
        market_conditions = {
            'market_correlation': None,  # BTC 상관관계 (필요 시)
            'flash_crash': None,         # 플래시 크래시 감지 (필요 시)
            'rsi_divergence': None       # RSI 다이버전스 (필요 시)
        }

        # AI 판단 검증
        validation_result = AIDecisionValidator.validate_decision(
            ai_result,
            technical_indicators,
            market_conditions
        )

        is_valid, validation_reason, override_decision = validation_result

        # 검증 결과 출력
        validation_report = AIDecisionValidator.generate_validation_report(
            validation_result,
            ai_result,
            technical_indicators
        )
        print(validation_report)

        # 검증 실패 시 AI 판단 오버라이드
        if not is_valid and override_decision:
            Logger.print_warning(f"⚠️ AI 판단 거부: {validation_reason}")
            ai_result['decision'] = override_decision
            ai_result['reason'] += f"\n[검증 레이어] {validation_reason}"
            ai_result['confidence'] = 'low'

        # ============================================
        # Step 5: 거래 실행 (기존 로직)
        # ============================================
        decision = ai_result["decision"]
        trade_result = None

        if decision == "buy":
            # Kelly Criterion 기반 포지션 사이징 (옵션)
            # 백테스트 성과 데이터가 있다면 활용
            # position_size = risk_manager.calculate_kelly_position_size(
            #     win_rate=0.6,
            #     avg_win=8.0,
            #     avg_loss=-4.0,
            #     current_capital=current_status['krw_balance']
            # )

            trade_result = trading_service.execute_buy(ticker)
            # 거래 기록 (손익은 나중에 계산)
            risk_manager.last_trade_time = datetime.now()
            risk_manager.daily_trade_count += 1

        elif decision == "sell":
            trade_result = trading_service.execute_sell(ticker)
            # 손익 계산 및 기록
            if position_info:
                pnl_pct = position_check['pnl_pct']
                risk_manager.record_trade(pnl_pct)

        elif decision == "hold":
            trading_service.execute_hold()

        # 결과 반환
        return {
            'status': 'success',
            'decision': ai_result.get('decision', 'hold'),
            'confidence': ai_result.get('confidence', 'medium'),
            'reason': ai_result.get('reason', ''),
            'validation': validation_reason,
            'risk_checks': {
                'position_check': position_check,
                'circuit_breaker': circuit_check,
                'frequency_check': frequency_check
            },
            'trade_result': trade_result
        }

    except Exception as e:
        Logger.print_error(f"거래 사이클 오류: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            'status': 'failed',
            'decision': 'hold',
            'error': str(e)
        }


# ============================================
# 사용 예제
# ============================================
async def main():
    """메인 함수"""
    ticker = TradingConfig.TICKER

    Logger.print_program_start(ticker)

    # 클라이언트 및 서비스 초기화
    upbit_client = UpbitClient()
    data_collector = DataCollector()
    trading_service = TradingService(upbit_client)
    ai_service = AIService()

    # 리스크 관리가 통합된 거래 사이클 실행
    result = await execute_trading_cycle_with_risk_management(
        ticker,
        upbit_client,
        data_collector,
        trading_service,
        ai_service
    )

    # 결과 출력
    if result['status'] == 'success':
        Logger.print_success(f"✅ 거래 사이클 완료: {result['decision']}")
    else:
        Logger.print_error(f"❌ 거래 사이클 실패: {result.get('error', 'Unknown')}")

    return result


if __name__ == "__main__":
    asyncio.run(main())
