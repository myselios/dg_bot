"""
AI 자동매매 프로그램 메인 진입점

┌─────────────────────────────────────────────────────────────┐
│                    실전 트레이딩 단계 (온라인)                     │
└─────────────────────────────────────────────────────────────┘

이 스크립트는 실전 트레이딩을 위한 메인 진입점입니다.
실시간 데이터를 수집하고 AI 분석을 수행하여 실제 거래를 실행합니다.

주요 프로세스:
1. 빠른 백테스팅 필터링 (룰 기반만, AI 호출 없음)
2. 전략 신호 직접 확인 (SignalAnalyzer 제거)
3. 환경 안전성 체크
4. 거래 실행

전략 개발 단계(오프라인 백테스팅)는 backtest.py를 사용하세요.

스케줄러 통합:
- execute_trading_cycle(): 스케줄러에서 호출 가능한 거래 사이클 함수
- main(): 단독 실행용 메인 함수 (비동기)
"""
import asyncio
from typing import Dict, Optional, Any
from src.config.settings import TradingConfig
from src.api.upbit_client import UpbitClient
from src.data.collector import DataCollector
from src.trading.service import TradingService
from src.trading.indicators import TechnicalIndicators
from src.trading.signal_analyzer import SignalAnalyzer
from src.ai.service import AIService
from src.ai.market_correlation import calculate_market_risk
from src.position.service import PositionService
from src.backtesting import QuickBacktestFilter, QuickBacktestConfig
from src.backtesting.rule_based_strategy import RuleBasedBreakoutStrategy
from src.utils.logger import Logger


def get_current_status(upbit_client: UpbitClient, ticker: str) -> Dict[str, float]:
    """
    현재 상태 정보 수집
    
    Args:
        upbit_client: Upbit 클라이언트
        ticker: 거래 종목
        
    Returns:
        현재 상태 딕셔너리
    """
    return {
        "krw_balance": upbit_client.get_balance("KRW"),
        "coin_balance": upbit_client.get_balance(ticker),
        "current_price": upbit_client.get_current_price(ticker)
    }


def print_final_balance(upbit_client: UpbitClient, ticker: str) -> None:
    """
    최종 잔고 출력
    
    Args:
        upbit_client: Upbit 클라이언트
        ticker: 거래 종목
    """
    Logger.print_header("최종 잔고")
    final_krw = upbit_client.get_balance("KRW")
    final_coin = upbit_client.get_balance(ticker)
    print(f"현금: {final_krw:,.0f}원")
    print(f"{ticker}: {final_coin:.8f}")
    print(Logger._separator())


async def execute_trading_cycle(
    ticker: str,
    upbit_client: UpbitClient,
    data_collector: DataCollector,
    trading_service: TradingService,
    ai_service: AIService
) -> Dict[str, Any]:
    """
    한 번의 거래 사이클 실행
    
    스케줄러 또는 main()에서 호출됩니다.
    
    Args:
        ticker: 거래 종목
        upbit_client: Upbit 클라이언트
        data_collector: 데이터 수집기
        trading_service: 거래 서비스
        ai_service: AI 서비스
        
    Returns:
        {
            'status': 'success' | 'failed',
            'decision': 'buy' | 'sell' | 'hold',
            'confidence': float,
            'reason': str,
            'price': float (optional),
            'amount': float (optional),
            'total': float (optional),
            'error': str (optional)
        }
    """
    try:
        # 1. 현재 투자 상태 조회
        balances = upbit_client.get_balances()
        if balances:
            # ETH만 표시 (TICKER에서 통화 추출: "KRW-ETH" -> "ETH")
            target_currency = ticker.split('-')[1] if '-' in ticker else None
            Logger.print_investment_status(balances, upbit_client, target_currency=target_currency)
        
        # 2. 오더북 정보 조회
        orderbook = data_collector.get_orderbook(ticker)
        
        # 3. 차트 데이터 조회 (Phase 2: BTC 데이터 포함)
        chart_data_with_btc = data_collector.get_chart_data_with_btc(ticker)
        if chart_data_with_btc is None:
            Logger.print_error("차트 데이터를 가져올 수 없어 프로그램을 종료합니다.")
            return {
                'status': 'failed',
                'decision': 'hold',
                'confidence': 'low',
                'reason': '차트 데이터 조회 실패',
                'error': '차트 데이터를 가져올 수 없습니다'
            }
        
        # ETH와 BTC 데이터 분리
        chart_data = chart_data_with_btc['eth']
        btc_chart_data = chart_data_with_btc['btc']
        
        Logger.print_success(f"✅ BTC 데이터 수집 완료 (일봉: {len(btc_chart_data['day'])}일)")
        
        # 3-1. 시장 상관관계 분석 (Phase 2: BTC 베타/알파 계산)
        market_correlation = calculate_market_risk(btc_chart_data['day'], chart_data['day'])
        
        Logger.print_header("📊 시장 상관관계 분석")
        print(f"BTC-ETH 베타: {market_correlation.get('beta', 1.0):.2f}")
        print(f"BTC-ETH 알파: {market_correlation.get('alpha', 0.0):.4f}")
        print(f"상관계수: {market_correlation.get('correlation', 0.0):.2f}")
        print(f"시장 리스크: {market_correlation.get('market_risk', 'unknown')}")
        print(f"판단 근거: {market_correlation.get('risk_reason', 'N/A')}")
        print(Logger._separator() + "\n")
        
        # 1단계: 빠른 백테스팅 필터링 (로컬 1년치 데이터 사용)
        quick_filter = QuickBacktestFilter()
        # chart_data를 None으로 전달하면 로컬 데이터를 사용하여 1년치 데이터 로드
        quick_backtest_result = quick_filter.run_quick_backtest(ticker, chart_data=None)
        
        # 필터링 조건 체크
        if not quick_backtest_result.passed:
            Logger.print_error(f"백테스팅 필터링 조건 미달: {quick_backtest_result.reason}")
            Logger.print_warning("거래를 중단합니다. 보유 포지션을 유지합니다.")
            return {
                'status': 'success',  # 시스템은 정상 작동, 다만 거래 안 함
                'decision': 'hold',
                'confidence': 'medium',
                'reason': f'백테스팅 필터링 실패: {quick_backtest_result.reason}',
                'price': 0,
                'amount': 0,
                'total': 0
            }
        
        Logger.print_success("✅ 백테스팅 필터링 조건 통과 - AI 심화 분석 진행")
        
        # 4. 현재 상태 정보 수집
        current_status = get_current_status(upbit_client, ticker)
        
        # 5. 오더북 요약 생성
        orderbook_summary = data_collector.get_orderbook_summary(orderbook)
        
        # 5-1. 공포탐욕지수 조회
        fear_greed_index = _get_fear_greed_index(data_collector)
        
        # 6. 기술적 지표 계산
        technical_indicators = TechnicalIndicators.get_latest_indicators(
            chart_data['day']
        )
        
        # 6-1. 플래시 크래시 감지 (Phase 2)
        flash_crash = TechnicalIndicators.detect_flash_crash(chart_data['day'])
        if flash_crash['detected']:
            Logger.print_warning(f"⚠️ 플래시 크래시 감지: {flash_crash['description']}")
        else:
            Logger.print_success(f"✅ 플래시 크래시 없음")
        
        # 6-2. RSI 다이버전스 감지 (Phase 2)
        rsi_divergence = TechnicalIndicators.detect_rsi_divergence(chart_data['day'])
        
        Logger.print_header("📉 RSI 다이버전스 분석")
        print(f"다이버전스 타입: {rsi_divergence.get('type', 'none')}")
        print(f"신뢰도: {rsi_divergence.get('confidence', 'low')}")
        print(f"설명: {rsi_divergence.get('description', 'N/A')}")
        print(Logger._separator() + "\n")
        
        # 6-3. 신호 분석 (베스트 프랙티스 기반)
        signal_analysis = _analyze_signals(
            technical_indicators,
            current_status.get('current_price')
        )
        
        # 7. 포지션 정보 조회
        position_service = PositionService(upbit_client)
        position_info = position_service.get_detailed_position(ticker)
        
        # 8. AI 분석 및 거래 실행 (Phase 2: 시장 상관관계, 플래시 크래시, RSI 다이버전스 추가)
        ai_result = _execute_ai_trading(
            ai_service,
            trading_service,
            upbit_client,
            ticker,
            chart_data,
            orderbook_summary,
            current_status,
            technical_indicators,
            position_info,
            fear_greed_index,
            quick_backtest_result,
            market_correlation=market_correlation,
            flash_crash=flash_crash,
            rsi_divergence=rsi_divergence
        )
        
        # 거래 결과 반환
        current_price = upbit_client.get_current_price(ticker)
        coin_balance = upbit_client.get_balance(ticker)
        
        response = {
            'status': 'success',
            'decision': ai_result.get('decision', 'hold') if ai_result else 'hold',
            'confidence': ai_result.get('confidence', 'medium') if ai_result else 'medium',
            'reason': ai_result.get('reason', '') if ai_result else '',
            'price': current_price,
            'amount': coin_balance,
            'total': current_price * coin_balance if current_price and coin_balance else 0,
            'flash_crash': flash_crash,  # 플래시 크래시 정보 추가
            'rsi_divergence': rsi_divergence,  # RSI 다이버전스 정보 추가
            'backtest_result': quick_backtest_result,  # 백테스팅 결과 추가
        }
        
        # 거래 ID 및 수수료 추가 (buy/sell인 경우)
        if ai_result and 'trade_id' in ai_result:
            response['trade_id'] = ai_result['trade_id']
            response['trade_success'] = ai_result.get('trade_success', False)
            response['fee'] = ai_result.get('fee', 0)
            if 'trade_error' in ai_result:
                response['trade_error'] = ai_result['trade_error']
        
        return response
        
    except Exception as e:
        Logger.print_error(f"거래 사이클 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'status': 'failed',
            'decision': 'hold',
            'error': str(e)
        }


async def main():
    """메인 함수 (단독 실행용)"""
    ticker = TradingConfig.TICKER
    
    # 프로그램 시작
    Logger.print_program_start(ticker)
    
    # 클라이언트 및 서비스 초기화
    upbit_client = UpbitClient()
    data_collector = DataCollector()
    trading_service = TradingService(upbit_client)
    ai_service = AIService()
    
    # 거래 사이클 실행
    result = await execute_trading_cycle(
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
    
    # 최종 잔고 출력
    print_final_balance(upbit_client, ticker)
    
    return result


def _get_fear_greed_index(data_collector: DataCollector) -> Optional[Dict]:
    """
    공포탐욕지수 조회 및 출력
    
    Args:
        data_collector: 데이터 수집기
        
    Returns:
        공포탐욕지수 딕셔너리 또는 None
    """
    fear_greed_index = data_collector.get_fear_greed_index()
    if fear_greed_index:
        Logger.print_header("😨😍 공포탐욕지수")
        print(f"지수: {fear_greed_index['value']}/100")
        print(f"분류: {fear_greed_index['classification']}")
        print(Logger._separator() + "\n")
    return fear_greed_index


def _analyze_signals(
    technical_indicators: Optional[Dict],
    current_price: Optional[float]
) -> Optional[Dict]:
    """
    신호 분석 수행 및 출력
    
    Args:
        technical_indicators: 기술적 지표 딕셔너리
        current_price: 현재 가격
        
    Returns:
        신호 분석 결과 딕셔너리 또는 None
    """
    if not technical_indicators or not current_price:
        return None
    
    signal_analysis = SignalAnalyzer.analyze_signals(
        technical_indicators,
        current_price
    )
    
    Logger.print_header("📊 신호 분석 결과")
    print(f"결정: {signal_analysis['decision']}")
    print(f"매수 점수: {signal_analysis['buy_score']:.1f}")
    print(f"매도 점수: {signal_analysis['sell_score']:.1f}")
    print(f"총 점수: {signal_analysis['total_score']:.1f}")
    print(f"신호 강도: {signal_analysis['signal_strength']:.1f}")
    print(f"신뢰도: {signal_analysis['confidence']}")
    print("\n주요 신호:")
    for signal in signal_analysis['signals'][:10]:  # 상위 10개만 출력
        print(f"  • {signal}")
    print(Logger._separator() + "\n")
    
    return signal_analysis


def _execute_ai_trading(
    ai_service: AIService,
    trading_service: TradingService,
    upbit_client: UpbitClient,
    ticker: str,
    chart_data: Dict,
    orderbook_summary: Dict,
    current_status: Dict[str, float],
    technical_indicators: Optional[Dict],
    position_info: Dict,
    fear_greed_index: Optional[Dict],
    quick_backtest_result,
    market_correlation: Optional[Dict] = None,
    flash_crash: Optional[Dict] = None,
    rsi_divergence: Optional[Dict] = None
) -> Optional[Dict]:
    """
    AI 분석 및 거래 실행 (Phase 2: 시장 상관관계, 플래시 크래시, RSI 다이버전스 추가)
    
    Args:
        ai_service: AI 서비스
        trading_service: 거래 서비스
        upbit_client: Upbit 클라이언트
        ticker: 거래 종목
        chart_data: 차트 데이터
        orderbook_summary: 오더북 요약
        current_status: 현재 상태
        technical_indicators: 기술적 지표
        position_info: 포지션 정보
        fear_greed_index: 공포탐욕지수
        quick_backtest_result: 빠른 백테스팅 결과
        market_correlation: 시장 상관관계 분석 (Phase 2)
        flash_crash: 플래시 크래시 감지 결과 (Phase 2)
        rsi_divergence: RSI 다이버전스 감지 결과 (Phase 2)
        
    Returns:
        AI 분석 결과 딕셔너리 또는 None
    """
    # AI 분석 데이터 준비 (백테스팅 결과 포함)
    backtest_summary = {
        'passed': quick_backtest_result.passed,
        'metrics': quick_backtest_result.metrics,
        'filter_results': quick_backtest_result.filter_results,
        'reason': quick_backtest_result.reason
    }
    
    analysis_data = ai_service.prepare_analysis_data(
        chart_data,
        orderbook_summary,
        current_status,
        technical_indicators,
        position_info,
        fear_greed_index,
        backtest_result=backtest_summary,
        market_correlation=market_correlation,
        flash_crash=flash_crash,
        rsi_divergence=rsi_divergence
    )
    
    # AI 분석 수행
    ai_result = ai_service.analyze(ticker, analysis_data)
    
    if ai_result is None:
        Logger.print_error("AI 분석을 수행할 수 없습니다.")
        return None
    
    # AI 판단 결과 출력
    Logger.print_decision(
        ai_result["decision"],
        ai_result["confidence"],
        ai_result["reason"]
    )
    
    # 현재 가격 및 잔고 출력
    current_price = upbit_client.get_current_price(ticker)
    krw_balance = upbit_client.get_balance("KRW")
    coin_balance = upbit_client.get_balance(ticker)
    
    if current_price:
        print(f"현재 {ticker} 가격: {current_price:,.0f}원")
    print(f"보유 현금: {krw_balance:,.0f}원")
    print(f"보유 {ticker}: {coin_balance:.8f}\n")
    
    # 매매 로직 실행
    decision = ai_result["decision"]
    trade_result = None
    
    if decision == "buy":
        trade_result = trading_service.execute_buy(ticker)
    elif decision == "sell":
        trade_result = trading_service.execute_sell(ticker)
    elif decision == "hold":
        trading_service.execute_hold()
    else:
        Logger.print_error(
            f"알 수 없는 판단: '{decision}' - 아무 작업도 수행하지 않습니다."
        )
    
    # AI 결과 + 거래 결과 반환
    result = {**ai_result}
    if trade_result:
        result.update({
            'trade_id': trade_result.get('trade_id'),
            'trade_success': trade_result.get('success', False),
            'fee': trade_result.get('fee', 0),
            'trade_error': trade_result.get('error')
        })
    
    return result


def execute_trading_decision(
    backtest_result: Dict[str, Any],
    chart_data: Dict,
    market_conditions: Dict[str, Any],
    portfolio: Optional[Any],
    ticker: str
) -> Dict[str, Any]:
    """
    백테스팅 우선 의사결정 구조
    
    핵심 원칙:
    - 백테스팅 통과 = 전략 작동 중
    - SignalAnalyzer는 무시하고 전략의 generate_signal() 직접 호출
    - 환경 안전성만 체크
    
    Args:
        backtest_result: 백테스팅 결과
        chart_data: 차트 데이터
        market_conditions: 시장 조건 (market_correlation, flash_crash, rsi_divergence)
        portfolio: 포트폴리오 (None이면 포지션 없음)
        ticker: 거래 종목
        
    Returns:
        {
            'decision': 'buy' | 'sell' | 'hold',
            'reason': str,
            'stop_loss': float (optional),
            'take_profit': float (optional),
            'position_size': float (optional)
        }
    """
    # 1단계: 백테스팅 필터 (최우선)
    if not backtest_result.get('passed', False):
        return {
            'decision': 'hold',
            'reason': '백테스팅 실패 - 전략 비활성화'
        }
    
    # 2단계: 백테스팅 통과 시, 전략의 진입 신호 직접 확인
    # ⚠️ SignalAnalyzer가 아니라 RuleBasedBreakoutStrategy.generate_signal() 호출
    strategy = RuleBasedBreakoutStrategy(
        ticker=ticker,
        risk_per_trade=0.02,
        max_position_size=0.5
    )
    
    strategy_signal = strategy.generate_signal(chart_data.get('day'), portfolio)
    
    if strategy_signal and strategy_signal.action == 'buy':
        # 전략이 직접 매수 신호를 냈음
        # 환경 안전성만 체크
        env_check = check_environment_safety(market_conditions)
        
        if env_check['safe']:
            return {
                'decision': 'buy',
                'reason': f"전략 진입 조건 충족: {strategy_signal.reason}",
                'stop_loss': strategy_signal.stop_loss,
                'take_profit': strategy_signal.take_profit,
                'position_size': strategy_signal.position_size
            }
        else:
            return {
                'decision': 'hold',
                'reason': f"진입 조건 충족했으나 환경 위험: {env_check['warning']}"
            }
    
    elif strategy_signal and strategy_signal.action == 'sell':
        # 전략이 매도 신호를 냈음 (포지션 있을 때)
        return {
            'decision': 'sell',
            'reason': f"전략 청산 조건: {strategy_signal.reason}"
        }
    
    else:
        # 전략이 진입/청산 조건 모두 미충족
        return {
            'decision': 'hold',
            'reason': '전략 진입 조건 미충족 (응축/돌파/거래량 체크)'
        }


def check_environment_safety(market_conditions: Dict[str, Any]) -> Dict[str, Any]:
    """
    환경 안전성 체크
    
    체크 항목:
    1. BTC 시장 리스크 (high = 위험)
    2. 플래시 크래시 감지 (detected = 위험)
    3. RSI 하락 다이버전스 (bearish_divergence = 위험)
    
    Args:
        market_conditions: 시장 조건 딕셔너리
        
    Returns:
        {
            'safe': bool,
            'warning': str  # 위험 요소 설명
        }
    """
    warnings = []
    
    # 1. BTC 시장 리스크 체크
    market_corr = market_conditions.get('market_correlation', {})
    if market_corr.get('market_risk') == 'high':
        warnings.append(f"시장 리스크 높음: {market_corr.get('risk_reason', 'BTC 급락')}")
    
    # 2. 플래시 크래시 체크
    flash_crash = market_conditions.get('flash_crash', {})
    if flash_crash.get('detected'):
        warnings.append(f"플래시 크래시 감지: {flash_crash.get('description', '급락')}")
    
    # 3. RSI 하락 다이버전스 체크
    rsi_div = market_conditions.get('rsi_divergence', {})
    if rsi_div.get('type') == 'bearish_divergence':
        warnings.append(f"RSI 하락 다이버전스: {rsi_div.get('description', '모멘텀 약화')}")
    
    if warnings:
        return {
            'safe': False,
            'warning': ' | '.join(warnings)
        }
    
    return {
        'safe': True,
        'warning': ''
    }


if __name__ == "__main__":
    # 비동기 실행
    asyncio.run(main())

