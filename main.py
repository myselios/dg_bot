"""
AI 자동매매 프로그램 메인 진입점

┌─────────────────────────────────────────────────────────────┐
│                    실전 트레이딩 단계 (온라인)                     │
└─────────────────────────────────────────────────────────────┘

이 스크립트는 실전 트레이딩을 위한 메인 진입점입니다.
실시간 데이터를 수집하고 AI 분석을 수행하여 실제 거래를 실행합니다.

리팩토링된 아키텍처:
- 파이프라인 패턴을 사용하여 거래 사이클을 단계별로 분리
- 각 스테이지는 독립적으로 실행되고 테스트 가능
- 선물 거래 확장을 위한 구조 마련

주요 프로세스 (파이프라인 스테이지):
1. RiskCheckStage: 리스크 관리 체크 (손절/익절, Circuit Breaker, 거래 빈도)
2. DataCollectionStage: 데이터 수집 (차트, 오더북, 기술적 지표)
3. AnalysisStage: 분석 (시장 상관관계, 백테스팅, AI 분석, 검증)
4. ExecutionStage: 거래 실행 (매수/매도/보류)

전략 개발 단계(오프라인 백테스팅)는 backtest.py를 사용하세요.

스케줄러 통합:
- execute_trading_cycle(): 스케줄러에서 호출 가능한 거래 사이클 함수
- main(): 단독 실행용 메인 함수 (비동기)
"""
import asyncio
from typing import Dict, Any
from src.config.settings import TradingConfig
from src.api.upbit_client import UpbitClient
from src.data.collector import DataCollector
from src.trading.service import TradingService
from src.ai.service import AIService
from src.trading.pipeline import create_spot_trading_pipeline, PipelineContext
from src.utils.logger import Logger


async def execute_trading_cycle(
    ticker: str,
    upbit_client: UpbitClient,
    data_collector: DataCollector,
    trading_service: TradingService,
    ai_service: AIService,
    trading_type: str = 'spot'
) -> Dict[str, Any]:
    """
    한 번의 거래 사이클 실행 (파이프라인 아키텍처)

    스케줄러 또는 main()에서 호출됩니다.

    파이프라인 스테이지:
    1. RiskCheckStage: 리스크 체크 (최우선) - 손절/익절, Circuit Breaker, 거래 빈도
    2. DataCollectionStage: 데이터 수집 - 차트, 오더북, 기술적 지표, 포지션
    3. AnalysisStage: 분석 - 시장 분석, 백테스팅, AI 분석, 검증
    4. ExecutionStage: 거래 실행 - 매수/매도/보류

    Args:
        ticker: 거래 종목
        upbit_client: Upbit 클라이언트
        data_collector: 데이터 수집기
        trading_service: 거래 서비스
        ai_service: AI 서비스
        trading_type: 거래 타입 ('spot' 또는 'futures')

    Returns:
        {
            'status': 'success' | 'failed' | 'blocked' | 'skipped',
            'decision': 'buy' | 'sell' | 'hold',
            'confidence': float,
            'reason': str,
            'validation': str,  # AI 검증 결과
            'risk_checks': Dict,  # 리스크 체크 결과
            'price': float (optional),
            'amount': float (optional),
            'total': float (optional),
            'error': str (optional),
            'pipeline_status': str  # 'completed' | 'failed'
        }
    """
    try:
        # 파이프라인 생성
        if trading_type == 'spot':
            pipeline = create_spot_trading_pipeline(
                stop_loss_pct=-5.0,
                take_profit_pct=10.0,
                daily_loss_limit_pct=-10.0,
                min_trade_interval_hours=4
            )
        else:
            # TODO: 선물 거래 파이프라인 구현
            raise NotImplementedError(f"거래 타입 '{trading_type}'는 아직 지원되지 않습니다.")

        # 컨텍스트 생성
        context = PipelineContext(
            ticker=ticker,
            trading_type=trading_type,
            upbit_client=upbit_client,
            data_collector=data_collector,
            trading_service=trading_service,
            ai_service=ai_service
        )

        # 파이프라인 실행
        result = await pipeline.execute(context)

        return result

    except Exception as e:
        Logger.print_error(f"거래 사이클 오류: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            'status': 'failed',
            'decision': 'hold',
            'error': str(e),
            'pipeline_status': 'failed'
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

    # 거래 사이클 실행 (파이프라인)
    result = await execute_trading_cycle(
        ticker,
        upbit_client,
        data_collector,
        trading_service,
        ai_service,
        trading_type='spot'
    )

    # 결과 출력
    if result.get('status') == 'success':
        Logger.print_success(f"✅ 거래 사이클 완료: {result.get('decision')}")
    else:
        Logger.print_error(f"❌ 거래 사이클 실패: {result.get('error', 'Unknown')}")

    # 최종 잔고 출력
    print_final_balance(upbit_client, ticker)

    return result


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


if __name__ == "__main__":
    # 비동기 실행
    asyncio.run(main())
