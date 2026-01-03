"""
AI 자동매매 프로그램 메인 진입점 (Thin Entrypoint)

이 스크립트는 TradingOrchestrator로 비즈니스 로직을 위임하는
얇은 진입점(thin entrypoint)입니다.

스케줄러 통합:
- execute_trading_cycle(): 스케줄러에서 호출 가능한 거래 사이클 함수 (레거시 호환)
- execute_position_management_cycle(): 포지션 관리 함수 (레거시 호환)
- main(): 단독 실행용 메인 함수 (비동기)

Note:
    실제 비즈니스 로직은 TradingOrchestrator에 있습니다.
    이 파일의 함수들은 backward compatibility를 위해 유지됩니다.
    Phase 4 완료 후 scheduler.py가 TradingOrchestrator를 직접 사용하면
    이 파일의 레거시 함수들은 deprecated 됩니다.
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
from src.utils.logger import Logger
from src.trading.pipeline import create_hybrid_trading_pipeline, PipelineContext


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
    liquidity_top_n: int = 10,
    min_volume_krw: float = 10_000_000_000,
    backtest_top_n: int = 5,
    final_select_n: int = 2,
    # 클린 아키텍처 의존성 컨테이너
    container: 'Container' = None,
    # 콜백 함수 (백테스팅 완료 후 호출)
    on_backtest_complete: callable = None
) -> Dict[str, Any]:
    """
    한 번의 거래 사이클 실행 (레거시 호환 래퍼)

    Note:
        이 함수는 backward compatibility를 위해 유지됩니다.
        내부적으로 TradingOrchestrator를 사용합니다.
        새 코드에서는 TradingOrchestrator를 직접 사용하세요.

    Args:
        ticker: 거래 종목
        upbit_client: Upbit 클라이언트
        data_collector: 데이터 수집기
        trading_service: 거래 서비스
        ai_service: AI 서비스
        trading_type: 거래 타입
        enable_scanning: 멀티코인 스캐닝 활성화 여부
        max_positions: 최대 동시 포지션 수
        stop_loss_pct: 손절 비율
        take_profit_pct: 익절 비율
        daily_loss_limit_pct: 일일 최대 손실 비율
        min_trade_interval_hours: 최소 거래 간격
        liquidity_top_n: 유동성 스캔 상위 N개
        min_volume_krw: 최소 거래대금
        backtest_top_n: 백테스팅 통과 상위 N개
        final_select_n: 최종 선택 N개
        container: 클린 아키텍처 의존성 컨테이너
        on_backtest_complete: 백테스트 완료 콜백

    Returns:
        거래 사이클 결과 Dict
    """
    # Container가 없으면 레거시 서비스로 생성
    if container is None:
        from src.container import Container
        container = Container.create_from_legacy(
            upbit_client=upbit_client,
            ai_service=ai_service,
            data_collector=data_collector
        )

    # TradingOrchestrator 사용
    from src.application.services.trading_orchestrator import TradingOrchestrator
    orchestrator = TradingOrchestrator(container=container)

    # 콜백 설정
    if on_backtest_complete:
        orchestrator.set_on_backtest_complete(on_backtest_complete)

    # 거래 사이클 실행
    return await orchestrator.execute_trading_cycle(
        ticker=ticker,
        trading_type=trading_type,
        enable_scanning=enable_scanning,
        max_positions=max_positions,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        daily_loss_limit_pct=daily_loss_limit_pct,
        min_trade_interval_hours=min_trade_interval_hours,
        liquidity_top_n=liquidity_top_n,
        min_volume_krw=min_volume_krw,
        backtest_top_n=backtest_top_n,
        final_select_n=final_select_n
    )


async def execute_position_management_cycle(
    upbit_client: UpbitClient = None,
    data_collector: DataCollector = None,
    trading_service: TradingService = None,
    # 리스크 관리 파라미터
    stop_loss_pct: float = -5.0,
    take_profit_pct: float = 10.0,
    max_positions: int = 3,
    # 클린 아키텍처 의존성 컨테이너
    container: 'Container' = None
) -> Dict[str, Any]:
    """
    포지션 관리 전용 사이클 실행 (레거시 호환 래퍼)

    Note:
        이 함수는 backward compatibility를 위해 유지됩니다.
        내부적으로 TradingOrchestrator를 사용합니다.
        새 코드에서는 TradingOrchestrator를 직접 사용하세요.

    Args:
        upbit_client: Upbit 클라이언트
        data_collector: 데이터 수집기
        trading_service: 거래 서비스
        stop_loss_pct: 손절 비율
        take_profit_pct: 익절 비율
        max_positions: 최대 동시 포지션 수
        container: 클린 아키텍처 의존성 컨테이너

    Returns:
        포지션 관리 결과 Dict
    """
    # Container가 없으면 레거시 서비스로 생성
    if container is None:
        from src.container import Container
        container = Container.create_from_legacy(
            upbit_client=upbit_client,
            ai_service=None,
            data_collector=data_collector
        )

    # TradingOrchestrator 사용
    from src.application.services.trading_orchestrator import TradingOrchestrator
    orchestrator = TradingOrchestrator(container=container)

    # 포지션 관리 실행
    return await orchestrator.execute_position_management(
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        max_positions=max_positions
    )


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

    # Container 초기화
    from src.container import Container
    container = Container.create_from_legacy(
        upbit_client=upbit_client,
        ai_service=ai_service,
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

    # 결과 출력
    if result.get('status') == 'success':
        Logger.print_success(f"거래 사이클 완료: {result.get('decision')}")
    else:
        Logger.print_error(f"거래 사이클 실패: {result.get('error', 'Unknown')}")

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
