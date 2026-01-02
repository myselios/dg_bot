"""
AI 자동매매 프로그램 메인 진입점

┌─────────────────────────────────────────────────────────────┐
│                    실전 트레이딩 단계 (온라인)                     │
└─────────────────────────────────────────────────────────────┘

이 스크립트는 실전 트레이딩을 위한 메인 진입점입니다.
실시간 데이터를 수집하고 AI 분석을 수행하여 실제 거래를 실행합니다.

하이브리드 파이프라인 아키텍처:
- 단일 파이프라인으로 모든 거래 시나리오를 처리
- 포지션 유무에 따른 자동 모드 분기 (ENTRY/MANAGEMENT/BLOCKED)
- 선택적 멀티코인 스캐닝 지원 (enable_scanning 파라미터)

주요 프로세스:
1. HybridRiskCheckStage: 포지션 상태 확인 및 모드 분기 + 코인 스캔 (옵션)
   - BLOCKED: 리스크 초과, 즉시 종료
   - MANAGEMENT: 포지션 관리 (규칙 기반 + AI 하이브리드)
   - ENTRY: 진입 모드 (선택적 코인 스캔)
2. DataCollectionStage: 데이터 수집 (차트, 오더북, 기술적 지표)
3. AnalysisStage: 분석 (시장 상관관계, 백테스팅, AI 분석, 검증)
4. ExecutionStage: 거래 실행 (매수/매도/보류)

전략 개발 단계(오프라인 백테스팅)는 backtest.py를 사용하세요.

스케줄러 통합:
- execute_trading_cycle(): 스케줄러에서 호출 가능한 거래 사이클 함수
- main(): 단독 실행용 메인 함수 (비동기)

멀티코인 지원:
- 최대 N개 코인 동시 보유 가능 (max_positions 설정)
- PortfolioManager로 포트폴리오 레벨 관리
"""
import asyncio
from typing import Dict, Any, TYPE_CHECKING
from src.config.settings import TradingConfig

if TYPE_CHECKING:
    from src.container import Container
from src.api.upbit_client import UpbitClient
from src.data.collector import DataCollector
from src.trading.service import TradingService
from src.ai.service import AIService
from src.trading.pipeline import (
    create_hybrid_trading_pipeline,
    create_position_management_pipeline,
    PipelineContext
)
from src.utils.logger import Logger


async def execute_trading_cycle(
    ticker: str,
    upbit_client: UpbitClient,
    data_collector: DataCollector,
    trading_service: TradingService,
    ai_service: AIService,
    trading_type: str = 'spot',
    enable_scanning: bool = True,
    max_positions: int = 3,
    # 리스크 관리 파라미터
    stop_loss_pct: float = -5.0,
    take_profit_pct: float = 10.0,
    daily_loss_limit_pct: float = -10.0,
    min_trade_interval_hours: int = 4,
    # 스캐너 파라미터
    liquidity_top_n: int = 20,
    min_volume_krw: float = 10_000_000_000,
    backtest_top_n: int = 5,
    final_select_n: int = 2,
    # 클린 아키텍처 의존성 컨테이너
    container: 'Container' = None
) -> Dict[str, Any]:
    """
    한 번의 거래 사이클 실행 (하이브리드 파이프라인)

    스케줄러 또는 main()에서 호출됩니다.
    단일 파이프라인으로 모든 거래 시나리오를 처리합니다.

    흐름:
    1. HybridRiskCheckStage: 포지션 상태 확인 및 모드 분기 + 코인 스캔 (옵션)
       - BLOCKED: 리스크 초과 → 즉시 종료
       - MANAGEMENT: 포지션 관리 (규칙 기반 + AI 하이브리드)
       - ENTRY: 진입 모드 (선택적 코인 스캔)
    2. DataCollectionStage: 데이터 수집
    3. AnalysisStage: 분석 (진입 모드에서만)
    4. ExecutionStage: 거래 실행

    Args:
        ticker: 거래 종목 (스캔 활성화 시 fallback 티커로 사용)
        upbit_client: Upbit 클라이언트
        data_collector: 데이터 수집기
        trading_service: 거래 서비스
        ai_service: AI 서비스
        trading_type: 거래 타입 ('spot' 또는 'futures')
        enable_scanning: 멀티코인 스캐닝 활성화 여부 (기본 True)
        max_positions: 최대 동시 포지션 수 (기본 3)
        stop_loss_pct: 손절 비율 (기본 -5%)
        take_profit_pct: 익절 비율 (기본 +10%)
        daily_loss_limit_pct: 일일 최대 손실 비율 (기본 -10%)
        min_trade_interval_hours: 최소 거래 간격 (기본 4시간)
        liquidity_top_n: 유동성 스캔 상위 N개 (기본 20)
        min_volume_krw: 최소 거래대금 (기본 100억원)
        backtest_top_n: 백테스팅 통과 상위 N개 (기본 5)
        final_select_n: 최종 선택 N개 (기본 2)

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
        # 거래 타입 검증
        if trading_type != 'spot':
            raise NotImplementedError(f"거래 타입 '{trading_type}'는 아직 지원되지 않습니다.")

        # 하이브리드 파이프라인 생성
        pipeline = create_hybrid_trading_pipeline(
            # 리스크 관리 파라미터
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            daily_loss_limit_pct=daily_loss_limit_pct,
            min_trade_interval_hours=min_trade_interval_hours,
            max_positions=max_positions,
            # 스캔 파라미터
            enable_scanning=enable_scanning,
            fallback_ticker=ticker,
            liquidity_top_n=liquidity_top_n,
            min_volume_krw=min_volume_krw,
            backtest_top_n=backtest_top_n,
            final_select_n=final_select_n
        )

        # 컨텍스트 생성
        context = PipelineContext(
            ticker=ticker,
            trading_type=trading_type,
            container=container,
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


async def execute_position_management_cycle(
    upbit_client: UpbitClient,
    data_collector: DataCollector,
    trading_service: TradingService,
    # 리스크 관리 파라미터
    stop_loss_pct: float = -5.0,
    take_profit_pct: float = 10.0,
    max_positions: int = 3
) -> Dict[str, Any]:
    """
    포지션 관리 전용 사이클 실행 (15분 주기용)

    기존 포지션의 손절/익절만 관리합니다.
    포지션이 없으면 즉시 종료합니다 (진입 로직 없음).

    Args:
        upbit_client: Upbit 클라이언트
        data_collector: 데이터 수집기
        trading_service: 거래 서비스
        stop_loss_pct: 손절 비율 (기본 -5%)
        take_profit_pct: 익절 비율 (기본 +10%)
        max_positions: 최대 동시 포지션 수 (기본 3)

    Returns:
        {
            'status': 'success' | 'skipped' | 'failed',
            'decision': 'sell' | 'hold',
            'positions_checked': int,
            'actions': List[Dict],  # 실행된 액션들
            'error': str (optional)
        }
    """
    try:
        Logger.print_header("🔄 포지션 관리 사이클 (15분)")

        # 포지션 관리 전용 파이프라인 생성
        pipeline = create_position_management_pipeline(
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            max_positions=max_positions
        )

        # 컨텍스트 생성 (ticker는 동적으로 결정됨)
        context = PipelineContext(
            ticker="KRW-BTC",  # placeholder, 실제로는 포지션에서 결정
            trading_type='spot',
            upbit_client=upbit_client,
            data_collector=data_collector,
            trading_service=trading_service,
            ai_service=None  # 포지션 관리는 AI 불필요
        )

        # 파이프라인 실행
        result = await pipeline.execute(context)

        # 결과에 포지션 관리 정보 추가
        result['cycle_type'] = 'position_management'

        return result

    except Exception as e:
        Logger.print_error(f"포지션 관리 사이클 오류: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            'status': 'failed',
            'decision': 'hold',
            'cycle_type': 'position_management',
            'error': str(e),
            'pipeline_status': 'failed'
        }


async def main():
    """메인 함수 (단독 실행용)"""
    ticker = TradingConfig.TICKER

    # 프로그램 시작
    Logger.print_program_start(ticker)

    # 클라이언트 및 서비스 초기화 (레거시)
    upbit_client = UpbitClient()
    data_collector = DataCollector()
    trading_service = TradingService(upbit_client)
    ai_service = AIService()

    # Container 초기화 (클린 아키텍처)
    # 레거시 서비스를 래핑하여 점진적 마이그레이션 지원
    from src.container import Container
    container = Container.create_from_legacy(
        upbit_client=upbit_client,
        ai_service=ai_service,
        data_collector=data_collector
    )

    # 거래 사이클 실행 (하이브리드 파이프라인)
    # enable_scanning=True: 멀티코인 스캐닝 활성화
    # enable_scanning=False: 고정 티커(ticker) 사용
    result = await execute_trading_cycle(
        ticker=ticker,
        upbit_client=upbit_client,
        data_collector=data_collector,
        trading_service=trading_service,
        ai_service=ai_service,
        trading_type='spot',
        enable_scanning=True,  # 멀티코인 스캐닝 활성화
        max_positions=3,
        container=container  # 클린 아키텍처 의존성 컨테이너
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
