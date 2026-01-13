"""
APScheduler 설정 및 관리
주기적인 트레이딩 작업을 스케줄링합니다.

Clean Architecture Migration (2026-01-03):
- Container를 통해 TradingOrchestrator 사용
- main.py 의존성 제거 (계층 분리)
- 레거시 서비스 추출 없이 Port/UseCase 직접 사용
"""
import asyncio
import logging
import pandas as pd
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.app.core.config import settings
from backend.app.services.notification import notify_scan_result

logger = logging.getLogger(__name__)

# ============================================================================
# Container 싱글톤 (Clean Architecture)
# ============================================================================
_container = None


def get_container():
    """
    Container 싱글톤 인스턴스 반환

    Clean Architecture:
    - AIService 제거 (Container.get_ai_port()가 OpenAIAdapter 기본 반환)
    - UpbitClient, DataCollector만 래핑 (레거시 호환성)
    - PostgreSQL session_factory를 전달하여 Lock/Idempotency 지원
    """
    global _container
    if _container is None:
        from src.container import Container
        from src.api.upbit_client import UpbitClient
        from src.data.collector import DataCollector
        from backend.app.db.session import AsyncSessionLocal

        # 레거시 서비스 생성 (UpbitClient, DataCollector만 유지)
        # AIService 제거 - Container.get_ai_port()가 OpenAIAdapter 기본 반환
        upbit_client = UpbitClient()
        data_collector = DataCollector()

        # Container로 래핑 (PostgreSQL session_factory 전달)
        _container = Container.create_from_legacy(
            upbit_client=upbit_client,
            data_collector=data_collector,
            session_factory=AsyncSessionLocal,
        )
        logger.info("✅ Container 싱글톤 초기화 완료 (Clean Architecture)")

    return _container


def get_trading_orchestrator():
    """
    TradingOrchestrator 인스턴스 반환

    Container를 통해 TradingOrchestrator를 획득합니다.
    main.py 의존성 없이 거래 사이클을 실행할 수 있습니다.
    """
    container = get_container()
    return container.get_trading_orchestrator()


def get_upbit_client():
    """
    UpbitClient 인스턴스 반환 (텔레그램 로깅용)

    Container 내부의 LegacyExchangeAdapter에서 UpbitClient를 추출합니다.
    """
    container = get_container()
    # LegacyExchangeAdapter._client에서 추출
    if container._exchange_port and hasattr(container._exchange_port, '_client'):
        return container._exchange_port._client
    return None


def get_data_collector():
    """
    DataCollector 인스턴스 반환 (텔레그램 로깅용)

    Container 내부의 LegacyMarketDataAdapter에서 DataCollector를 추출합니다.
    """
    container = get_container()
    # LegacyMarketDataAdapter._collector에서 추출
    if container._market_data_port and hasattr(container._market_data_port, '_collector'):
        return container._market_data_port._collector
    return None


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
    1. Lock 획득 (동시 실행 방지)
    2. TradingOrchestrator 초기화
    3. execute_trading_cycle() 호출
    4. 결과 DB 저장
    5. Telegram 알림 전송
    6. 메트릭 기록

    Clean Architecture:
    - main.py 의존성 제거
    - TradingOrchestrator를 통해 거래 사이클 실행
    - Lock/Idempotency로 안정성 확보
    """
    from src.config.settings import TradingConfig
    from backend.app.services.notification import (
        notify_error,
        notify_cycle_start,
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

    # Container 및 Lock/Idempotency Port 획득
    container = get_container()
    lock_port = container.get_lock_port()
    lock_acquired = False

    try:
        # Lock 획득 시도 (trading_cycle 락)
        lock_acquired = await lock_port.acquire("trading_cycle", timeout_seconds=600)
        if not lock_acquired:
            logger.warning("⚠️ trading_cycle 락 획득 실패 - 다른 작업이 실행 중입니다")
            scheduler_job_failure_total.labels(job_name='trading_job').inc()
            return

        logger.info("🔒 trading_cycle 락 획득 완료")
        logger.info(f"[{datetime.now()}] 트레이딩 작업 시작")

        # 1. TradingOrchestrator 초기화 (Clean Architecture)
        ticker = TradingConfig.TICKER
        orchestrator = get_trading_orchestrator()

        logger.info(f"✅ TradingOrchestrator 초기화 완료 (심볼: {ticker})")

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

            # Container에서 레거시 서비스 추출 (텔레그램 로그용)
            upbit_client = get_upbit_client()
            data_collector = get_data_collector()

            if not upbit_client or not data_collector:
                raise RuntimeError("레거시 서비스를 가져올 수 없습니다")

            current_price = upbit_client.get_current_price(ticker)
            orderbook = upbit_client.get_orderbook(ticker)
            # DataCollector.get_chart_data는 {'day': df, 'minute60': df, 'minute15': df} 반환
            chart_data_dict = data_collector.get_chart_data(ticker)
            chart_data = chart_data_dict.get('day') if chart_data_dict else None
            if chart_data is None:
                logger.warning("차트 데이터 수집 실패")
                raise RuntimeError("차트 데이터를 가져올 수 없습니다")
            
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
            """백테스팅 완료 후 텔레그램 알림 전송 (스캔 결과 + 백테스팅)"""
            try:
                bt_ticker = backtest_data.get('ticker', ticker)
                bt_result = backtest_data.get('backtest_result', {})
                flash_crash = backtest_data.get('flash_crash')
                rsi_divergence = backtest_data.get('rsi_divergence')
                scan_summary = backtest_data.get('scan_summary', {})
                selected_coin = backtest_data.get('selected_coin')
                all_backtest_results = backtest_data.get('all_backtest_results', [])
                technical_indicators = backtest_data.get('technical_indicators', {})

                # 스캔 요약 로깅
                logger.info(f"📊 백테스팅 콜백 데이터:")
                logger.info(f"  - 티커: {bt_ticker}")
                logger.info(f"  - 스캔: {scan_summary.get('liquidity_scanned', 0)}개 → 통과: {scan_summary.get('backtest_passed', 0)}개")
                logger.info(f"  - 최고점수: {scan_summary.get('best_score', 0)}")
                logger.info(f"  - 선택 코인: {selected_coin}")
                logger.info(f"  - metrics: {bt_result.get('metrics', {})}")

                # 📱 1) 스캔 결과 알림 (유동성 + 백테스팅 요약)
                try:
                    await notify_scan_result(
                        scan_summary=scan_summary,
                        selected_coin=selected_coin,
                        all_backtest_results=all_backtest_results,
                    )
                    logger.info("✅ 스캔 결과 알림 전송 완료")
                except Exception as scan_error:
                    logger.warning(f"스캔 결과 알림 전송 실패: {scan_error}")

                # 📱 2) 백테스팅 상세 알림 제거 (notify_scan_result에서 이미 표시)
                # flash_crash, rsi_divergence가 있으면 별도 경고만 로깅
                if flash_crash and flash_crash.get('detected'):
                    logger.warning(f"⚠️ 플래시 크래시 감지: {flash_crash.get('description', '')}")
                if rsi_divergence and rsi_divergence.get('type') != 'none':
                    logger.info(f"📊 RSI 다이버전스: {rsi_divergence.get('type')}")

                logger.info("✅ 스캔 결과 알림 전송 완료 (백테스팅 + Trading Pass 포함)")
            except Exception as e:
                logger.warning(f"백테스팅 알림 전송 실패: {e}", exc_info=True)

        # 3. 거래 사이클 실행 (TradingOrchestrator 사용) - 10분 타임아웃
        TRADING_CYCLE_TIMEOUT = 600  # 10분

        # 콜백 설정
        orchestrator.set_on_backtest_complete(on_backtest_complete_callback)

        try:
            result = await asyncio.wait_for(
                orchestrator.execute_trading_cycle(
                    ticker=ticker,
                    trading_type='spot',
                    enable_scanning=True,  # 멀티코인 스캐닝 활성화
                    max_positions=3,
                ),
                timeout=TRADING_CYCLE_TIMEOUT
            )
        except asyncio.TimeoutError:
            error_msg = f"거래 사이클 타임아웃 ({TRADING_CYCLE_TIMEOUT}초)"
            logger.error(f"⏰ {error_msg}")

            # 타임아웃 에러 알림
            try:
                await notify_error(
                    error_type="Trading Cycle Timeout",
                    error_message=error_msg,
                    context={"ticker": ticker, "timeout_seconds": TRADING_CYCLE_TIMEOUT}
                )
            except Exception as telegram_error:
                logger.warning(f"타임아웃 에러 알림 전송 실패: {telegram_error}")

            # 기본 결과 반환
            result = {
                'status': 'failed',
                'decision': 'hold',
                'reason': error_msg,
                'error': error_msg
            }

        # 스캔된 코인 정보 추출 (멀티코인 스캐닝 결과)
        selected_coin = result.get('selected_coin', {})
        actual_ticker = selected_coin.get('ticker') if selected_coin else ticker
        actual_symbol = selected_coin.get('symbol', ticker.replace('KRW-', '')) if selected_coin else ticker.replace('KRW-', '')

        # 스캔 결과 로깅
        if selected_coin:
            logger.info(f"🎯 스캔 선택 코인: {actual_symbol} (점수: {selected_coin.get('score', 'N/A')})")
        else:
            # 멀티코인 스캔에서 선택된 코인이 없으면 HOLD (고정 티커 사용 X)
            logger.info(f"⏭️ 스캔 결과: 선택된 코인 없음 → HOLD")

        # 📱 사이클 시작 알림은 이미 스캐닝 시작 전에 전송됨
        # 백테스팅 결과 알림은 on_backtest_complete_callback에서 전송됨

        # 4. 결과 처리
        status = result.get('status', 'failed')
        if status == 'success':
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
            
            # 포트폴리오 정보 수집 (전체 포지션 포함)
            positions_info = []
            total_invested = 0.0
            total_value = 0.0
            krw_balance = 0.0
            trading_mode = "entry"
            can_open_new_position = True

            try:
                _upbit_client = get_upbit_client()
                if not _upbit_client:
                    raise RuntimeError("UpbitClient를 가져올 수 없습니다")

                balances = _upbit_client.get_balances()
                MIN_POSITION_VALUE = 10000  # 최소 포지션 가치

                if balances:
                    for balance in balances:
                        currency = balance['currency']
                        amount = float(balance['balance'])
                        avg_buy_price = float(balance['avg_buy_price'])

                        if currency == 'KRW':
                            krw_balance = amount
                        elif amount > 0 and avg_buy_price > 0:
                            invested = amount * avg_buy_price
                            if invested < MIN_POSITION_VALUE:
                                continue

                            ticker = f'KRW-{currency}'
                            try:
                                current_price = _upbit_client.get_current_price(ticker)
                                if current_price:
                                    value = amount * current_price
                                    pnl = ((current_price - avg_buy_price) / avg_buy_price * 100)

                                    positions_info.append({
                                        'symbol': currency,
                                        'ticker': ticker,
                                        'invested': invested,
                                        'value': value,
                                        'pnl': pnl,
                                    })
                                    total_invested += invested
                                    total_value += value
                            except:
                                pass

                # 거래 모드 및 진입 가능 여부 결정
                max_positions = 3
                position_count = len(positions_info)
                if position_count >= max_positions:
                    trading_mode = "management"
                    can_open_new_position = False
                elif position_count > 0:
                    trading_mode = "entry"
                    can_open_new_position = krw_balance >= MIN_POSITION_VALUE
                else:
                    trading_mode = "entry"
                    can_open_new_position = krw_balance >= MIN_POSITION_VALUE

                logger.info(f"✅ 포트폴리오 수집: {position_count}개 포지션, 투자 {total_invested:,.0f} KRW")
            except Exception as portfolio_error:
                logger.warning(f"포트폴리오 정보 수집 실패: {portfolio_error}")

            # result에 추가 정보 포함
            result['market_data'] = market_data
            result['portfolio'] = {
                'krw_balance': krw_balance,
                'total_invested': total_invested,
                'total_value': total_value,
                'positions': positions_info,
            }

            # 실행 시간 계산
            duration = time() - job_start_time

            # 📱 통합 트레이딩 사이클 완료 알림 (로그와 동일한 형태)
            try:
                from backend.app.services.notification import notify_trading_cycle_complete

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

                await notify_trading_cycle_complete(
                    decision=result['decision'],
                    reason=result.get('reason', '분석 중'),
                    positions=positions_info,
                    krw_balance=krw_balance,
                    total_invested=total_invested,
                    total_value=total_value,
                    trading_mode=trading_mode,
                    can_open_new_position=can_open_new_position,
                    max_positions=max_positions,
                    duration=duration,
                    trade_result=trade_result_data,
                )
                logger.info("✅ 트레이딩 사이클 완료 알림 전송")
            except Exception as telegram_error:
                logger.warning(f"트레이딩 사이클 완료 알림 전송 실패: {telegram_error}")
            
            # 성공 메트릭
            scheduler_job_success_total.labels(job_name='trading_job').inc()
            
        elif status == 'skipped':
            # Idempotency 스킵 (정상 동작)
            duration = time() - job_start_time
            logger.info(f"⏭️ 거래 사이클 스킵: {result.get('reason', '중복 실행 방지')}")
            logger.info(f"   이전 실행이 같은 시간봉에 이미 완료되었습니다.")
            # 스킵은 성공으로 카운트 (정상 동작이므로)
            scheduler_job_success_total.labels(job_name='trading_job').inc()

        else:
            # 실패 처리
            error_msg = result.get('error', result.get('reason', 'Unknown error'))
            logger.error(f"❌ 거래 사이클 실패: {error_msg}")

            # 실행 시간 계산
            duration = time() - job_start_time

            # 📱 실패 시 에러 알림만 전송
            try:
                await notify_error(
                    error_type="Trading Cycle Failed",
                    error_message=error_msg,
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

    finally:
        # Lock 해제 (반드시 실행)
        if lock_acquired:
            await lock_port.release("trading_cycle")
            logger.info("🔓 trading_cycle 락 해제 완료")


async def position_management_job():
    """
    포지션 관리 작업 (15분마다)

    기존 포지션의 손절/익절을 관리합니다.
    포지션이 없으면 즉시 종료합니다 (진입 로직 없음).

    Clean Architecture:
    - main.py 의존성 제거
    - TradingOrchestrator를 통해 포지션 관리 실행
    - Lock으로 trading_job과 상호 배제
    """
    from backend.app.services.notification import (
        notify_error,
        notify_cycle_start,
        notify_position_status,
        notify_position_exit,
    )
    from backend.app.services.metrics import (
        scheduler_job_duration_seconds,
        scheduler_job_success_total,
        scheduler_job_failure_total
    )
    from time import time

    job_start_time = time()

    # Container 및 Lock Port 획득
    container = get_container()
    lock_port = container.get_lock_port()
    lock_acquired = False

    try:
        # Lock 획득 시도 (trading_cycle 락 - trading_job과 동일한 락 사용)
        # 60초 타임아웃으로 trading_job이 끝날 때까지 대기
        lock_acquired = await lock_port.acquire("trading_cycle", timeout_seconds=60)
        if not lock_acquired:
            logger.warning("⚠️ trading_cycle 락 획득 실패 - trading_job이 실행 중입니다. 스킵합니다.")
            scheduler_job_success_total.labels(job_name='position_management_job').inc()
            return

        logger.info("🔒 position_management 락 획득 완료")
        logger.info(f"[{datetime.now()}] 포지션 관리 작업 시작 (15분 주기)")

        # 📱 1) 포지션 관리 시작 알림
        try:
            await notify_cycle_start(
                symbol="포지션 관리",
                status="started",
                message="보유 포지션 손절/익절 체크를 시작합니다 (15분 주기)"
            )
            logger.info("✅ 포지션 관리 시작 알림 전송 완료")
        except Exception as telegram_error:
            logger.warning(f"포지션 관리 시작 알림 전송 실패: {telegram_error}")

        # 📊 포지션 정보 수집 (텔레그램 알림용)
        positions_info = []
        total_invested = 0.0
        total_value = 0.0
        krw_balance = 0.0

        try:
            upbit_client = get_upbit_client()
            if upbit_client:
                balances = upbit_client.get_balances()

                # 최소 포지션 가치 (1만원 이하는 무시)
                MIN_POSITION_VALUE = 10000

                for balance in balances:
                    currency = balance['currency']
                    amount = float(balance['balance'])
                    avg_buy_price = float(balance['avg_buy_price'])

                    if currency == 'KRW':
                        krw_balance = amount
                    elif amount > 0 and avg_buy_price > 0:
                        # 투자 금액 계산
                        invested = amount * avg_buy_price

                        # 최소 포지션 가치 미만은 무시 (먼지 잔고 필터링)
                        if invested < MIN_POSITION_VALUE:
                            continue

                        # 암호화폐 포지션
                        ticker = f'KRW-{currency}'
                        try:
                            current_price = upbit_client.get_current_price(ticker)
                            if current_price:
                                value = amount * current_price
                                pnl = ((current_price - avg_buy_price) / avg_buy_price * 100) if avg_buy_price > 0 else 0

                                positions_info.append({
                                    'symbol': currency,
                                    'ticker': ticker,
                                    'invested': invested,
                                    'value': value,
                                    'pnl': pnl,
                                    'amount': amount,
                                    'avg_buy_price': avg_buy_price,
                                    'current_price': current_price,
                                })

                                total_invested += invested
                                total_value += value
                        except:
                            pass

                logger.info(f"✅ 포지션 정보 수집 완료: {len(positions_info)}개 포지션")
        except Exception as position_error:
            logger.warning(f"포지션 정보 수집 실패: {position_error}")

        # 📱 2) 포지션 상태 알림
        try:
            await notify_position_status(
                positions=positions_info,
                total_invested=total_invested,
                total_value=total_value,
                krw_balance=krw_balance,
            )
            logger.info("✅ 포지션 상태 알림 전송 완료")
        except Exception as telegram_error:
            logger.warning(f"포지션 상태 알림 전송 실패: {telegram_error}")

        # TradingOrchestrator 초기화 (Clean Architecture)
        orchestrator = get_trading_orchestrator()

        # 포지션 관리 사이클 실행
        result = await orchestrator.execute_position_management()

        # 결과 처리
        duration = time() - job_start_time

        if result.get('status') == 'success':
            actions = result.get('actions', [])
            exit_actions = [a for a in actions if a.get('action') in ['exit', 'partial_exit']]

            if exit_actions:
                logger.info(f"✅ 포지션 관리 완료: {len(exit_actions)}개 포지션 청산")

                # 📱 3) 청산 알림 전송
                for action in exit_actions:
                    try:
                        symbol = action.get('symbol', 'N/A')
                        exit_type = action.get('exit_type', 'unknown')  # 'stop_loss' 또는 'take_profit'
                        reason = action.get('reason', '포지션 청산')

                        # 포지션 정보에서 투자금액 및 PnL 찾기
                        pos_info = next((p for p in positions_info if p['symbol'] == symbol.replace('KRW-', '')), None)

                        if pos_info:
                            invested = pos_info['invested']
                            exit_value = pos_info['value']
                            pnl = pos_info['pnl']

                            await notify_position_exit(
                                symbol=symbol,
                                exit_type=exit_type,
                                invested=invested,
                                exit_value=exit_value,
                                pnl=pnl,
                                reason=reason,
                            )
                            logger.info(f"✅ {symbol} 청산 알림 전송 완료")
                    except Exception as telegram_error:
                        logger.warning(f"청산 알림 전송 실패: {telegram_error}")
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

    finally:
        # Lock 해제 (반드시 실행)
        if lock_acquired:
            await lock_port.release("trading_cycle")
            logger.info("🔓 position_management 락 해제 완료")


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
    """
    스케줄러에 작업 추가 (CronTrigger 기반)

    CronTrigger를 사용하여 캔들 마감 시점에 정렬된 실행을 보장합니다.
    버퍼 시간(기본 1분)은 캔들 데이터 안정화를 위해 적용됩니다.

    실행 시점:
    - trading_job: 매시 01분 (1시간봉 마감 + 1분 버퍼)
    - position_management_job: :01, :16, :31, :46 (15분봉 마감 + 1분 버퍼)
    - portfolio_snapshot_job: 매시 01분
    - daily_report_job: 매일 09:00
    """
    from src.config.settings import SchedulerConfig

    if not settings.SCHEDULER_ENABLED:
        logger.warning("스케줄러가 비활성화되어 있습니다.")
        return

    # 1. 트레이딩 작업 (매시 N분 - 1시간봉 마감 + 버퍼)
    scheduler.add_job(
        trading_job,
        trigger=CronTrigger(
            minute=SchedulerConfig.TRADING_JOB_MINUTE,
            timezone="Asia/Seoul"
        ),
        id="trading_job",
        name=f"트레이딩 작업 - 진입 탐색 (매시 {SchedulerConfig.TRADING_JOB_MINUTE:02d}분)",
        replace_existing=True,
    )
    logger.info(f"✅ 트레이딩 작업 등록됨 (CronTrigger: 매시 {SchedulerConfig.TRADING_JOB_MINUTE:02d}분)")

    # 2. 포지션 관리 작업 (15분봉 마감 + 버퍼)
    scheduler.add_job(
        position_management_job,
        trigger=CronTrigger(
            minute=SchedulerConfig.POSITION_JOB_MINUTES,
            timezone="Asia/Seoul"
        ),
        id="position_management_job",
        name=f"포지션 관리 작업 - 손절/익절 (:{SchedulerConfig.POSITION_JOB_MINUTES})",
        replace_existing=True,
    )
    logger.info(f"✅ 포지션 관리 작업 등록됨 (CronTrigger: :{SchedulerConfig.POSITION_JOB_MINUTES})")

    # 3. 포트폴리오 스냅샷 (매시 N분)
    scheduler.add_job(
        portfolio_snapshot_job,
        trigger=CronTrigger(
            minute=SchedulerConfig.PORTFOLIO_JOB_MINUTE,
            timezone="Asia/Seoul"
        ),
        id="portfolio_snapshot_job",
        name=f"포트폴리오 스냅샷 저장 (매시 {SchedulerConfig.PORTFOLIO_JOB_MINUTE:02d}분)",
        replace_existing=True,
    )
    logger.info(f"✅ 포트폴리오 스냅샷 작업 등록됨 (CronTrigger: 매시 {SchedulerConfig.PORTFOLIO_JOB_MINUTE:02d}분)")

    # 4. 일일 리포트 (매일 N시 M분)
    scheduler.add_job(
        daily_report_job,
        trigger=CronTrigger(
            hour=SchedulerConfig.DAILY_REPORT_HOUR,
            minute=SchedulerConfig.DAILY_REPORT_MINUTE,
            timezone="Asia/Seoul"
        ),
        id="daily_report_job",
        name=f"일일 리포트 전송 (매일 {SchedulerConfig.DAILY_REPORT_HOUR:02d}:{SchedulerConfig.DAILY_REPORT_MINUTE:02d})",
        replace_existing=True,
    )
    logger.info(f"✅ 일일 리포트 작업 등록됨 (CronTrigger: 매일 {SchedulerConfig.DAILY_REPORT_HOUR:02d}:{SchedulerConfig.DAILY_REPORT_MINUTE:02d})")


def start_scheduler():
    """
    스케줄러 시작

    SCHEDULER_RUN_IMMEDIATELY 설정이 true인 경우:
    - 스케줄러 시작 직후 trading_job을 즉시 실행
    - 개발/테스트 환경에서 유용

    프로덕션에서는 SCHEDULER_RUN_IMMEDIATELY=false로 설정하여
    CronTrigger 스케줄에 따라 실행되도록 함
    """
    from src.config.settings import SchedulerConfig

    if scheduler.running:
        logger.warning("스케줄러가 이미 실행 중입니다.")
        return

    add_jobs()
    scheduler.start()
    logger.info("✅ 스케줄러 시작됨 (CronTrigger 기반)")

    # 즉시 실행 옵션 (개발/테스트용)
    if SchedulerConfig.RUN_IMMEDIATELY:
        logger.info("🚀 즉시 실행 모드 활성화 - 트레이딩 작업 즉시 실행")
        # 일회성 즉시 실행 작업 추가 (misfire 방지를 위해 별도 작업으로)
        from datetime import timedelta
        from zoneinfo import ZoneInfo

        # 명시적으로 Asia/Seoul timezone 사용 (컨테이너 TZ와 무관하게 안전)
        kst = ZoneInfo("Asia/Seoul")
        run_at = datetime.now(kst) + timedelta(seconds=2)

        scheduler.add_job(
            trading_job,
            'date',
            run_date=run_at,
            id='trading_job_immediate',
            name='트레이딩 작업 - 즉시 실행 (일회성)',
            replace_existing=True,
            misfire_grace_time=60
        )
        logger.info(f"✅ 트레이딩 작업이 {run_at.strftime('%H:%M:%S')} KST에 즉시 실행되도록 예약됨")
    else:
        # 다음 실행 시간 로깅
        trading_job_info = scheduler.get_job('trading_job')
        if trading_job_info and trading_job_info.next_run_time:
            logger.info(f"⏰ 다음 트레이딩 작업 실행 예정: {trading_job_info.next_run_time.strftime('%Y-%m-%d %H:%M:%S')}")


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

