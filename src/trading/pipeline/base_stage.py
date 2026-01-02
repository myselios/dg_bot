"""
트레이딩 파이프라인 베이스 스테이지

각 스테이지는 입력을 받아 처리하고 다음 스테이지로 전달할 출력을 생성합니다.
이 구조는 선물/현물 거래 확장을 용이하게 합니다.

NOTE: 모든 스테이지는 async/await 패턴을 사용합니다.
      UseCase들이 async이므로 파이프라인도 async로 통일합니다.

MIGRATION NOTE (2026-01-02):
    Container 기반 클린 아키텍처로 마이그레이션 완료.
    - 스테이지들은 Container가 있으면 UseCase를 사용
    - Container가 없으면 레거시 서비스들을 사용 (하위 호환성)
    - trading_service, ai_service 필드는 deprecated - 향후 제거 예정
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
import warnings


@dataclass
class PipelineContext:
    """
    파이프라인 전체에서 공유되는 컨텍스트

    각 스테이지는 이 컨텍스트를 읽고 수정할 수 있습니다.
    """
    # 거래 기본 정보
    ticker: str
    trading_type: str = 'spot'  # 'spot' or 'futures'

    # 의존성 컨테이너 (클린 아키텍처 - 권장)
    # Container를 통해 UseCase에 접근합니다.
    # 예: context.container.get_execute_trade_use_case()
    container: Any = None

    # 레거시 서비스 인스턴스 (DEPRECATED - 향후 제거 예정)
    # Container와 UseCase 사용을 권장합니다.
    # 마이그레이션 완료 후 이 필드들은 제거됩니다.
    upbit_client: Any = None  # DEPRECATED: Container.get_exchange_port() 사용
    data_collector: Any = None  # DEPRECATED: Container.get_market_data_port() 사용
    trading_service: Any = None  # DEPRECATED: Container.get_execute_trade_use_case() 사용
    ai_service: Any = None  # DEPRECATED: Container.get_analyze_market_use_case() 사용

    # 수집된 데이터
    chart_data: Optional[Dict] = None
    btc_chart_data: Optional[Dict] = None
    orderbook: Optional[Dict] = None
    orderbook_summary: Optional[Dict] = None
    technical_indicators: Optional[Dict] = None
    current_status: Optional[Dict] = None
    position_info: Optional[Dict] = None
    fear_greed_index: Optional[Dict] = None

    # 분석 결과
    market_correlation: Optional[Dict] = None
    flash_crash: Optional[Dict] = None
    rsi_divergence: Optional[Dict] = None
    signal_analysis: Optional[Dict] = None
    backtest_result: Optional[Any] = None
    ai_result: Optional[Dict] = None
    validation_result: Optional[tuple] = None

    # 리스크 관리
    risk_manager: Optional[Any] = None
    position_check: Optional[Dict] = None
    circuit_check: Optional[Dict] = None
    frequency_check: Optional[Dict] = None

    # 거래 실행 결과
    trade_result: Optional[Dict] = None

    # 메타데이터
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class StageResult:
    """
    스테이지 실행 결과

    Attributes:
        success: 성공 여부
        action: 수행된 액션 ('continue', 'skip', 'stop', 'exit')
        data: 다음 스테이지로 전달할 데이터
        message: 결과 메시지
        metadata: 추가 메타데이터
    """
    success: bool
    action: str  # 'continue', 'skip', 'stop', 'exit'
    data: Optional[Dict[str, Any]] = None
    message: str = ""
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.data is None:
            self.data = {}
        if self.metadata is None:
            self.metadata = {}


class BasePipelineStage(ABC):
    """
    파이프라인 스테이지 베이스 클래스

    모든 파이프라인 스테이지는 이 클래스를 상속받아 구현합니다.
    각 스테이지는 단일 책임을 가지며, 독립적으로 테스트 가능합니다.
    """

    def __init__(self, name: str):
        """
        Args:
            name: 스테이지 이름 (로깅용)
        """
        self.name = name

    @abstractmethod
    async def execute(self, context: PipelineContext) -> StageResult:
        """
        스테이지 실행 (비동기)

        Args:
            context: 파이프라인 컨텍스트

        Returns:
            StageResult: 실행 결과
        """
        pass

    def pre_execute(self, context: PipelineContext) -> bool:
        """
        실행 전 검증 (오버라이드 가능)

        Args:
            context: 파이프라인 컨텍스트

        Returns:
            bool: 실행 가능 여부
        """
        return True

    def post_execute(self, context: PipelineContext, result: StageResult) -> None:
        """
        실행 후 처리 (오버라이드 가능)

        Args:
            context: 파이프라인 컨텍스트
            result: 실행 결과
        """
        pass

    def handle_error(self, context: PipelineContext, error: Exception) -> StageResult:
        """
        에러 핸들링 (오버라이드 가능)

        Args:
            context: 파이프라인 컨텍스트
            error: 발생한 에러

        Returns:
            StageResult: 에러 처리 결과
        """
        return StageResult(
            success=False,
            action='stop',
            message=f"{self.name} 스테이지 오류: {str(error)}",
            metadata={'error': str(error), 'error_type': type(error).__name__}
        )
