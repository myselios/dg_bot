"""
APScheduler 설정 및 관리
주기적인 트레이딩 작업을 스케줄링합니다.
"""
import logging
import pandas as pd
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# 전역 스케줄러 인스턴스
scheduler = AsyncIOScheduler(
    timezone="Asia/Seoul",
    job_defaults={
        "coalesce": True,  # 누락된 작업 병합
        "max_instances": 1,  # 동시 실행 방지
        "misfire_grace_time": 60,  # 지연 허용 시간 (초)
    }
)


async def trading_job():
    """
    주기적 트레이딩 작업 (1시간마다)
    
    실행 순서:
    1. 서비스 초기화
    2. execute_trading_cycle() 호출
    3. 결과 DB 저장 (TODO)
    4. Telegram 알림 전송
    5. 메트릭 기록
    """
    # Import는 함수 내부에서 수행 (순환 참조 방지)
    from main import execute_trading_cycle
    from src.api.upbit_client import UpbitClient
    from src.data.collector import DataCollector
    from src.trading.service import TradingService
    from src.ai.service import AIService
    from src.config.settings import TradingConfig
    from backend.app.services.notification import (
        notify_trade,
        notify_error,
        notify_cycle_start,  # 1) 사이클 시작 알림
        notify_backtest_and_signals,  # 2) 백테스팅 및 신호 분석
        notify_ai_decision,  # 3) AI 의사결정 상세
        notify_portfolio_status,  # 4) 포트폴리오 현황
    )
    from backend.app.services.metrics import (
        record_ai_decision,
        record_trade,  # H-2: 거래 메트릭 기록용
        scheduler_job_duration_seconds,
        scheduler_job_success_total,
        scheduler_job_failure_total
    )
    from time import time
    
    job_start_time = time()
    
    try:
        logger.info(f"[{datetime.now()}] 트레이딩 작업 시작")
        
        # 1. 서비스 초기화
        ticker = TradingConfig.TICKER
        upbit_client = UpbitClient()
        data_collector = DataCollector()
        trading_service = TradingService(upbit_client)
        ai_service = AIService()
        
        logger.info(f"✅ 서비스 초기화 완료 (심볼: {ticker})")

        # 📱 1) 사이클 시작 알림 (스캐닝 시작 전)
        try:
            await notify_cycle_start(
                symbol="멀티코인",
                status="started",
                message="멀티코인 스캐닝 및 트레이딩 사이클을 시작합니다"
            )
            logger.info("✅ 사이클 시작 알림 전송 완료")
        except Exception as telegram_error:
            logger.warning(f"사이클 시작 알림 전송 실패: {telegram_error}")

        # 2. 시장 데이터 수집 (텔레그램 로그용)
        market_data = {}
        try:
            # 기술적 지표 import (함수 내부에서 import하여 순환 참조 방지)
            from src.trading.indicators import TechnicalIndicators
            
            current_price = upbit_client.get_current_price(ticker)
            orderbook = upbit_client.get_orderbook(ticker)
            chart_data = data_collector.collect_market_data(
                ticker, 
                interval='day', 
                count=60
            )
            
            # 기술적 지표 계산
            # chart_data의 컬럼명 확인 (trade_price 또는 close)
            price_col = 'trade_price' if 'trade_price' in chart_data.columns else 'close'
            
            rsi_series = TechnicalIndicators.calculate_rsi(chart_data, period=14, column=price_col)
            rsi_value = rsi_series.iloc[-1] if len(rsi_series) > 0 and not pd.isna(rsi_series.iloc[-1]) else 50.0
            
            ma_20_series = TechnicalIndicators.calculate_ma(chart_data, period=20, column=price_col)
            ma_20 = ma_20_series.iloc[-1] if len(ma_20_series) > 0 and not pd.isna(ma_20_series.iloc[-1]) else (chart_data.iloc[-1][price_col] if len(chart_data) > 0 else 0.0)
            
            ma_60_series = TechnicalIndicators.calculate_ma(chart_data, period=60, column=price_col)
            ma_60 = ma_60_series.iloc[-1] if len(ma_60_series) > 0 and not pd.isna(ma_60_series.iloc[-1]) else (chart_data.iloc[-1][price_col] if len(chart_data) > 0 else 0.0)
            
            # 24시간 변동률
            if len(chart_data) >= 2:
                prev_close = chart_data.iloc[-2]['trade_price']
                current = chart_data.iloc[-1]['trade_price']
                change_rate = ((current - prev_close) / prev_close) * 100
            else:
                change_rate = 0.0
            
            market_data = {
                'current_price': current_price,
                'volume_24h': chart_data.iloc[-1]['candle_acc_trade_volume'] if len(chart_data) > 0 else 0,
                'change_rate': change_rate,
                'rsi': rsi_value,
                'ma_20': ma_20,
                'ma_60': ma_60,
            }
            logger.info(f"✅ 시장 데이터 수집 완료: 현재가 {current_price:,.0f} KRW, RSI {rsi_value:.2f}")
        except Exception as market_error:
            logger.warning(f"시장 데이터 수집 실패: {market_error}")
            # market_data는 이미 {} 로 초기화되어 있음

        # 📱 백테스팅 완료 콜백 정의 (AI 분석 전에 호출됨)
        async def on_backtest_complete_callback(backtest_data: dict):
            """백테스팅 완료 후 텔레그램 알림 전송"""
            try:
                bt_ticker = backtest_data.get('ticker', ticker)
                bt_result = backtest_data.get('backtest_result', {})
                flash_crash = backtest_data.get('flash_crash')
                rsi_divergence = backtest_data.get('rsi_divergence')
                scan_summary = backtest_data.get('scan_summary', {})

                # 스캔 요약 로깅
                logger.info(f"📊 백테스팅 콜백 데이터:")
                logger.info(f"  - 티커: {bt_ticker}")
                logger.info(f"  - 스캔: {scan_summary.get('liquidity_scanned', 0)}개 → 통과: {scan_summary.get('backtest_passed', 0)}개")
                logger.info(f"  - 최고점수: {scan_summary.get('best_score', 0)}")
                logger.info(f"  - metrics: {bt_result.get('metrics', {})}")

                await notify_backtest_and_signals(
                    symbol=bt_ticker,
                    backtest_result=bt_result,
                    market_data=market_data,
                    flash_crash=flash_crash,
                    rsi_divergence=rsi_divergence,
                )
                logger.info("✅ 백테스팅 결과 알림 전송 완료 (AI 분석 전)")
            except Exception as e:
                logger.warning(f"백테스팅 알림 전송 실패: {e}", exc_info=True)

        # 3. 거래 사이클 실행 (하이브리드 파이프라인)
        result = await execute_trading_cycle(
            ticker=ticker,
            upbit_client=upbit_client,
            data_collector=data_collector,
            trading_service=trading_service,
            ai_service=ai_service,
            trading_type='spot',
            enable_scanning=True,  # 멀티코인 스캐닝 활성화
            max_positions=3,
            on_backtest_complete=on_backtest_complete_callback
        )

        # 스캔된 코인 정보 추출 (멀티코인 스캐닝 결과)
        selected_coin = result.get('selected_coin', {})
        actual_ticker = selected_coin.get('ticker') if selected_coin else ticker
        actual_symbol = selected_coin.get('symbol', ticker.replace('KRW-', '')) if selected_coin else ticker.replace('KRW-', '')

        # 스캔 결과 로깅
        if selected_coin:
            logger.info(f"🎯 스캔 선택 코인: {actual_symbol} (점수: {selected_coin.get('score', 'N/A')})")
        else:
            logger.info(f"📌 고정 티커 사용: {ticker}")

        # 📱 사이클 시작 알림은 이미 스캐닝 시작 전에 전송됨
        # 백테스팅 결과 알림은 on_backtest_complete_callback에서 전송됨

        # 4. 결과 처리
        if result['status'] == 'success':
            logger.info(f"✅ 거래 사이클 성공: {result['decision']}")
            
            # 메트릭 기록 (다이어그램 01-overall-system-flow.mmd)
            confidence_map = {'high': 0.8, 'medium': 0.5, 'low': 0.3}
            confidence_value = confidence_map.get(result.get('confidence', 'medium'), 0.5)
            
            # AI 판단 메트릭 (Prometheus) - 실제 선택된 코인 사용
            record_ai_decision(
                symbol=actual_ticker,
                decision=result['decision'],
                confidence=confidence_value
            )
            
            # AI 판단 PostgreSQL 저장 (모든 결정 저장: buy/sell/hold)
            try:
                from backend.app.schemas.ai_decision import AIDecisionCreate
                from backend.app.models.ai_decision import AIDecision
                from backend.app.db.session import get_db
                from decimal import Decimal
                
                # AIDecisionCreate 스키마 생성 - 실제 선택된 코인 사용
                ai_decision_data = AIDecisionCreate(
                    symbol=actual_ticker,
                    decision=result['decision'],
                    confidence=Decimal(str(confidence_value * 100)),  # 0-1 -> 0-100%
                    reason=result.get('reason', '')[:500],  # 500자 제한
                    market_data=result.get('market_data', {})  # 시장 데이터 (선택)
                )
                
                # DB에 저장
                async for db in get_db():
                    try:
                        db_ai_decision = AIDecision(**ai_decision_data.model_dump())
                        db.add(db_ai_decision)
                        await db.commit()
                        await db.refresh(db_ai_decision)
                        logger.info(f"✅ AI 판단 DB 저장 완료: {result['decision']} (ID: {db_ai_decision.id})")
                    except Exception as db_error:
                        await db.rollback()
                        logger.error(f"AI 판단 DB 저장 실패: {db_error}", exc_info=True)
                    break  # 첫 번째 DB 세션만 사용
            except Exception as e:
                logger.error(f"AI 판단 저장 중 오류: {e}", exc_info=True)
            
            # 거래 메트릭 (매수/매도 성공 시만 기록) - 실제 선택된 코인 사용
            if result['decision'] in ['buy', 'sell'] and result.get('trade_success', False):
                record_trade(
                    symbol=actual_ticker,
                    side=result['decision'],
                    volume=float(result.get('total', 0)),
                    fee=float(result.get('fee', 0))
                )
                logger.info(f"✅ 거래 메트릭 기록 완료: {actual_symbol} {result['decision']}")
            
            # PostgreSQL에 거래 기록 저장 (매수/매도인 경우)
            # API 호출을 통해 저장 (다이어그램 04-database-save-flow.mmd와 일치)
            if result['decision'] in ['buy', 'sell'] and result.get('trade_id'):
                try:
                    from backend.app.schemas.trade import TradeCreate
                    from backend.app.db.session import get_db
                    from backend.app.api.v1.endpoints.trades import create_trade
                    from decimal import Decimal
                    
                    # TradeCreate 스키마 생성 (검증 포함) - 실제 선택된 코인 사용
                    trade_data = TradeCreate(
                        trade_id=result['trade_id'],
                        symbol=actual_ticker,
                        side=result['decision'],
                        price=Decimal(str(result.get('price', 0))),
                        amount=Decimal(str(result.get('amount', 0))),
                        total=Decimal(str(result.get('total', 0))),
                        fee=Decimal(str(result.get('fee', 0))),
                        status='completed' if result.get('trade_success', False) else 'failed'
                    )
                    
                    # API 함수 직접 호출 (내부 호출이므로 HTTP 오버헤드 없음)
                    async for db in get_db():
                        try:
                            await create_trade(trade_data, db)
                            logger.info(f"✅ 거래 내역 API 저장 완료: {result['trade_id']}")
                        except Exception as api_error:
                            # 중복 거래 ID 등의 API 검증 오류 처리
                            if "이미 존재하는 거래 ID" in str(api_error):
                                logger.warning(f"중복 거래 ID: {result['trade_id']}")
                            else:
                                logger.error(f"거래 내역 API 저장 실패: {api_error}", exc_info=True)
                        break  # 첫 번째 DB 세션만 사용
                except Exception as e:
                    logger.error(f"거래 내역 저장 실패: {e}", exc_info=True)
            
            # 포트폴리오 정보 수집 (텔레그램 로그용) - 실제 선택된 코인 사용
            try:
                # 전체 잔고 조회 (get_balances 사용)
                balances = upbit_client.get_balances()

                # KRW 잔고 찾기
                krw_balance = 0.0
                crypto_balance = 0.0
                crypto_currency = actual_symbol  # 실제 선택된 코인 심볼 사용
                
                if balances:
                    for balance in balances:
                        if balance['currency'] == 'KRW':
                            krw_balance = float(balance['balance'])
                        elif balance['currency'] == crypto_currency:
                            crypto_balance = float(balance['balance'])
                
                # 현재가 조회 - 실제 선택된 코인
                current_price = upbit_client.get_current_price(actual_ticker)
                
                total_value = krw_balance + (crypto_balance * current_price if current_price else 0)
                
                portfolio_data = {
                    'krw_balance': krw_balance,
                    'crypto_balance': crypto_balance,
                    'total_value': total_value,
                }
                logger.info(f"✅ 포트폴리오 정보 수집 완료: 총 자산 {total_value:,.0f} KRW")
            except Exception as portfolio_error:
                logger.warning(f"포트폴리오 정보 수집 실패: {portfolio_error}")
                portfolio_data = {}
            
            # result에 추가 정보 포함
            result['market_data'] = market_data
            result['portfolio'] = portfolio_data
            
            # 실행 시간 계산
            duration = time() - job_start_time

            # 📱 2) 백테스팅 알림은 콜백에서 AI 분석 전에 이미 전송됨 (on_backtest_complete_callback)

            # 📱 3) AI 의사결정 상세 알림 (전체 텍스트) - 실제 선택된 코인 사용
            try:
                await notify_ai_decision(
                    symbol=actual_ticker,  # 실제 선택된 코인 사용
                    decision=result['decision'],
                    confidence=result.get('confidence', 'medium'),
                    reason=result.get('reason', '분석 중'),
                    duration=duration,
                )
                logger.info("✅ AI 의사결정 상세 알림 전송 완료")
            except Exception as telegram_error:
                logger.warning(f"AI 의사결정 알림 전송 실패: {telegram_error}")
            
            # 📱 4) 포트폴리오 현황 알림 - 실제 선택된 코인 사용
            try:
                # 거래 결과 (매수/매도인 경우)
                trade_result_data = None
                if result['decision'] in ['buy', 'sell'] and result.get('trade_id'):
                    trade_result_data = {
                        'trade_success': result.get('trade_success', False),
                        'trade_id': result.get('trade_id'),
                        'price': result.get('price'),
                        'amount': result.get('amount'),
                        'total': result.get('total'),
                        'fee': result.get('fee'),
                    }

                await notify_portfolio_status(
                    symbol=actual_ticker,  # 실제 선택된 코인 사용
                    portfolio_data=portfolio_data,
                    trade_result=trade_result_data,
                )
                logger.info("✅ 포트폴리오 현황 알림 전송 완료")
            except Exception as telegram_error:
                logger.warning(f"포트폴리오 알림 전송 실패: {telegram_error}")
            
            # 성공 메트릭
            scheduler_job_success_total.labels(job_name='trading_job').inc()
            
        else:
            # 실패 처리
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"❌ 거래 사이클 실패: {error_msg}")
            
            # 실행 시간 계산
            duration = time() - job_start_time
            
            # 📱 실패 시 에러 알림만 전송
            try:
                await notify_error(
                    error_type="Trading Cycle Failed",
                    error_message=result.get('error', 'Unknown error'),
                    context={'symbol': ticker, 'duration': f'{duration:.2f}초'}
                )
                logger.info("✅ 에러 알림 전송 완료")
            except Exception as telegram_error:
                logger.warning(f"에러 알림 전송 실패: {telegram_error}")
            
            # 실패 메트릭
            scheduler_job_failure_total.labels(job_name='trading_job').inc()
        
        # 5. 실행 시간 기록
        if 'duration' not in locals():
            duration = time() - job_start_time
        scheduler_job_duration_seconds.labels(job_name='trading_job').observe(duration)
        
        logger.info(f"✅ 트레이딩 작업 완료 (소요 시간: {duration:.2f}초)")
        
    except Exception as e:
        logger.error(f"❌ 트레이딩 작업 중 예외 발생: {e}", exc_info=True)
        
        # 실행 시간 계산
        duration = time() - job_start_time
        
        # Sentry로 에러 전송
        if settings.SENTRY_ENABLED:
            import sentry_sdk
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("component", "scheduler")
                scope.set_tag("job", "trading_job")
                scope.set_context("trading_context", {
                    "ticker": TradingConfig.TICKER,
                    "timestamp": datetime.now().isoformat(),
                })
                sentry_sdk.capture_exception(e)
        
        # 📱 예외 발생 시 에러 알림 전송
        try:
            await notify_error(
                error_type=type(e).__name__,
                error_message=str(e),
                context={'symbol': TradingConfig.TICKER, 'duration': f'{duration:.2f}초'}
            )
            logger.info("✅ 예외 에러 알림 전송 완료")
        except Exception as telegram_error:
            logger.warning(f"예외 에러 알림 전송 실패: {telegram_error}")
        
        # 실패 메트릭
        scheduler_job_failure_total.labels(job_name='trading_job').inc()


async def position_management_job():
    """
    포지션 관리 작업 (15분마다)

    기존 포지션의 손절/익절을 관리합니다.
    포지션이 없으면 즉시 종료합니다 (진입 로직 없음).
    """
    from main import execute_position_management_cycle
    from src.api.upbit_client import UpbitClient
    from src.data.collector import DataCollector
    from src.trading.service import TradingService
    from backend.app.services.notification import notify_error
    from backend.app.services.metrics import (
        scheduler_job_duration_seconds,
        scheduler_job_success_total,
        scheduler_job_failure_total
    )
    from time import time

    job_start_time = time()

    try:
        logger.info(f"[{datetime.now()}] 포지션 관리 작업 시작 (15분 주기)")

        # 서비스 초기화
        upbit_client = UpbitClient()
        data_collector = DataCollector()
        trading_service = TradingService(upbit_client)

        # 포지션 관리 사이클 실행
        result = await execute_position_management_cycle(
            upbit_client=upbit_client,
            data_collector=data_collector,
            trading_service=trading_service
        )

        # 결과 처리
        duration = time() - job_start_time

        if result.get('status') == 'success':
            actions = result.get('actions', [])
            exit_actions = [a for a in actions if a.get('action') in ['exit', 'partial_exit']]

            if exit_actions:
                logger.info(f"✅ 포지션 관리 완료: {len(exit_actions)}개 포지션 청산")
                # TODO: 청산 알림 전송
            else:
                logger.info(f"✅ 포지션 관리 완료: 변동 없음")

            scheduler_job_success_total.labels(job_name='position_management_job').inc()

        elif result.get('status') == 'skipped':
            logger.info(f"⏭️ 포지션 관리 스킵: {result.get('reason', '포지션 없음')}")
            scheduler_job_success_total.labels(job_name='position_management_job').inc()

        else:
            logger.error(f"❌ 포지션 관리 실패: {result.get('error', 'Unknown')}")
            scheduler_job_failure_total.labels(job_name='position_management_job').inc()

        scheduler_job_duration_seconds.labels(job_name='position_management_job').observe(duration)
        logger.info(f"✅ 포지션 관리 작업 완료 (소요 시간: {duration:.2f}초)")

    except Exception as e:
        logger.error(f"❌ 포지션 관리 작업 중 예외 발생: {e}", exc_info=True)

        duration = time() - job_start_time
        scheduler_job_failure_total.labels(job_name='position_management_job').inc()

        # Sentry로 에러 전송
        if settings.SENTRY_ENABLED:
            import sentry_sdk
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("component", "scheduler")
                scope.set_tag("job", "position_management_job")
                sentry_sdk.capture_exception(e)

        # 에러 알림
        try:
            await notify_error(
                error_type=type(e).__name__,
                error_message=str(e),
                context={'job': 'position_management_job', 'duration': f'{duration:.2f}초'}
            )
        except Exception as telegram_error:
            logger.warning(f"에러 알림 전송 실패: {telegram_error}")


async def portfolio_snapshot_job():
    """
    포트폴리오 스냅샷 저장 작업
    
    주기적으로 현재 포트폴리오 가치를 기록합니다.
    """
    try:
        logger.info(f"[{datetime.now()}] 포트폴리오 스냅샷 저장 시작")
        
        # TODO: 포트폴리오 스냅샷 저장 로직
        # from backend.app.services.portfolio_service import save_portfolio_snapshot
        # await save_portfolio_snapshot()
        
        logger.info("포트폴리오 스냅샷 저장 완료")
    except Exception as e:
        logger.error(f"포트폴리오 스냅샷 저장 중 오류 발생: {e}", exc_info=True)
        
        # Sentry로 에러 전송
        if settings.SENTRY_ENABLED:
            import sentry_sdk
            sentry_sdk.capture_exception(e)


async def daily_report_job():
    """
    일일 리포트 작업 (매일 오전 9시)
    
    전날 거래 통계를 집계하여 Telegram으로 전송합니다.
    """
    try:
        logger.info(f"[{datetime.now()}] 일일 리포트 생성 시작")
        
        from backend.app.services.notification import notify_daily_report
        from decimal import Decimal
        
        # TODO: 실제 DB에서 통계 조회
        # from backend.app.db.session import get_db
        # from sqlalchemy import select, func
        # from backend.app.models.trade import Trade
        # from datetime import timedelta
        # 
        # yesterday_start = datetime.now() - timedelta(days=1)
        # yesterday_start = yesterday_start.replace(hour=0, minute=0, second=0, microsecond=0)
        # yesterday_end = yesterday_start.replace(hour=23, minute=59, second=59)
        # 
        # async with get_db() as db:
        #     # 거래 통계 조회
        #     result = await db.execute(
        #         select(
        #             func.count(Trade.id).label('total_trades'),
        #             func.sum(Trade.profit_loss).label('total_profit'),
        #         ).where(
        #             Trade.created_at >= yesterday_start,
        #             Trade.created_at <= yesterday_end
        #         )
        #     )
        #     stats = result.one()
        
        # 임시 데이터 (DB 연동 전)
        total_trades = 24  # 24시간 동안 24번 판단
        profit_loss = Decimal("15000")  # 1.5만원 수익
        profit_rate = Decimal("1.5")  # 1.5% 수익률
        current_value = Decimal("1015000")  # 101.5만원
        
        # Telegram으로 리포트 전송
        await notify_daily_report(
            total_trades=total_trades,
            profit_loss=profit_loss,
            profit_rate=profit_rate,
            current_value=current_value
        )
        
        logger.info("✅ 일일 리포트 전송 완료")
        
    except Exception as e:
        logger.error(f"일일 리포트 작업 중 오류 발생: {e}", exc_info=True)
        
        # Sentry로 에러 전송
        if settings.SENTRY_ENABLED:
            import sentry_sdk
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("component", "scheduler")
                scope.set_tag("job", "daily_report_job")
                sentry_sdk.capture_exception(e)
        
        # 에러 알림
        from backend.app.services.notification import notify_error
        try:
            await notify_error(
                error_type=type(e).__name__,
                error_message=str(e),
                context={'job': 'daily_report_job', 'timestamp': datetime.now().isoformat()}
            )
        except Exception as telegram_error:
            logger.warning(f"Telegram 에러 알림 전송 실패: {telegram_error}")


def add_jobs():
    """스케줄러에 작업 추가"""
    
    if not settings.SCHEDULER_ENABLED:
        logger.warning("스케줄러가 비활성화되어 있습니다.")
        return
    
    # 현재 시각 (즉시 실행을 위해)
    now = datetime.now()
    
    # 1. 트레이딩 작업 (1시간마다 실행 - 진입 탐색용)
    scheduler.add_job(
        trading_job,
        trigger=IntervalTrigger(
            minutes=settings.SCHEDULER_INTERVAL_MINUTES,
            start_date=now  # 즉시 실행
        ),
        id="trading_job",
        name="트레이딩 작업 - 진입 탐색 (1시간)",
        replace_existing=True,
    )
    logger.info(f"✅ 트레이딩 작업 등록됨 (주기: {settings.SCHEDULER_INTERVAL_MINUTES}분 = 1시간, 즉시 실행)")

    # 2. 포지션 관리 작업 (15분마다 실행 - 손절/익절 관리용)
    scheduler.add_job(
        position_management_job,
        trigger=IntervalTrigger(
            minutes=15,
            start_date=now  # 즉시 실행
        ),
        id="position_management_job",
        name="포지션 관리 작업 - 손절/익절 (15분)",
        replace_existing=True,
    )
    logger.info("✅ 포지션 관리 작업 등록됨 (주기: 15분, 즉시 실행)")
    
    # 3. 포트폴리오 스냅샷 (매 시간, 즉시 실행)
    scheduler.add_job(
        portfolio_snapshot_job,
        trigger=IntervalTrigger(
            hours=1,
            start_date=now  # 즉시 실행
        ),
        id="portfolio_snapshot_job",
        name="포트폴리오 스냅샷 저장",
        replace_existing=True,
    )
    logger.info("✅ 포트폴리오 스냅샷 작업 등록됨 (주기: 1시간, 즉시 실행)")
    
    # 4. 일일 리포트 (매일 오전 9시)
    scheduler.add_job(
        daily_report_job,
        trigger=CronTrigger(hour=9, minute=0, timezone="Asia/Seoul"),
        id="daily_report_job",
        name="일일 리포트 전송",
        replace_existing=True,
    )
    logger.info("✅ 일일 리포트 작업 등록됨 (시간: 매일 09:00)")


def start_scheduler():
    """스케줄러 시작"""
    if scheduler.running:
        logger.warning("스케줄러가 이미 실행 중입니다.")
        return
    
    add_jobs()
    scheduler.start()
    logger.info("✅ 스케줄러 시작됨")
    
    # 스케줄러 시작 직후 트레이딩 작업 즉시 실행
    logger.info("🚀 트레이딩 작업 즉시 실행 중...")
    scheduler.modify_job('trading_job', next_run_time=datetime.now())
    logger.info("✅ 트레이딩 작업이 즉시 실행되도록 예약됨")


def stop_scheduler():
    """스케줄러 중지"""
    if not scheduler.running:
        logger.warning("스케줄러가 실행 중이 아닙니다.")
        return
    
    scheduler.shutdown(wait=True)
    logger.info("✅ 스케줄러 중지됨")


def pause_job(job_id: str):
    """특정 작업 일시 정지"""
    scheduler.pause_job(job_id)
    logger.info(f"작업 '{job_id}' 일시 정지됨")


def resume_job(job_id: str):
    """특정 작업 재개"""
    scheduler.resume_job(job_id)
    logger.info(f"작업 '{job_id}' 재개됨")


def get_jobs():
    """현재 등록된 모든 작업 조회"""
    jobs = scheduler.get_jobs()
    return [
        {
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if hasattr(job, 'next_run_time') and job.next_run_time else None,
            "trigger": str(job.trigger),
        }
        for job in jobs
    ]

