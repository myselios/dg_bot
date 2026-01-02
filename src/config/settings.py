"""
자동매매 시스템 설정
환경 변수 우선 사용, 검증 로직 포함
"""
import os
from typing import Optional
from dotenv import load_dotenv
from src.exceptions import ConfigurationError

load_dotenv()


def get_env_int(key: str, default: int, min_value: Optional[int] = None, max_value: Optional[int] = None) -> int:
    """환경 변수에서 정수 값 가져오기 (검증 포함)"""
    value = os.getenv(key)
    if value is None:
        return default
    
    try:
        int_value = int(value)
        if min_value is not None and int_value < min_value:
            raise ConfigurationError(key, f"값이 최소값({min_value})보다 작습니다: {int_value}")
        if max_value is not None and int_value > max_value:
            raise ConfigurationError(key, f"값이 최대값({max_value})보다 큽니다: {int_value}")
        return int_value
    except ValueError:
        raise ConfigurationError(key, f"정수로 변환할 수 없습니다: {value}")


def get_env_float(key: str, default: float, min_value: Optional[float] = None, max_value: Optional[float] = None) -> float:
    """환경 변수에서 실수 값 가져오기 (검증 포함)"""
    value = os.getenv(key)
    if value is None:
        return default
    
    try:
        float_value = float(value)
        if min_value is not None and float_value < min_value:
            raise ConfigurationError(key, f"값이 최소값({min_value})보다 작습니다: {float_value}")
        if max_value is not None and float_value > max_value:
            raise ConfigurationError(key, f"값이 최대값({max_value})보다 큽니다: {float_value}")
        return float_value
    except ValueError:
        raise ConfigurationError(key, f"실수로 변환할 수 없습니다: {value}")


def get_env_str(key: str, default: str) -> str:
    """환경 변수에서 문자열 값 가져오기"""
    return os.getenv(key, default)


class TradingConfig:
    """거래 설정"""
    TICKER = get_env_str("TRADING_TICKER", "KRW-ETH")
    MIN_ORDER_AMOUNT = get_env_int("TRADING_MIN_ORDER_AMOUNT", 5000, min_value=1000)
    FEE_RATE = get_env_float("TRADING_FEE_RATE", 0.0005, min_value=0.0, max_value=0.01)  # 0.05%
    MIN_FEE = get_env_int("TRADING_MIN_FEE", 5000, min_value=0)
    BUY_PERCENTAGE = get_env_float("TRADING_BUY_PERCENTAGE", 0.3, min_value=0.0, max_value=1.0)  # 30%
    SELL_PERCENTAGE = get_env_float("TRADING_SELL_PERCENTAGE", 1.0, min_value=0.0, max_value=1.0)  # 100%
    
    @classmethod
    def validate(cls):
        """거래 설정 검증"""
        if cls.MIN_ORDER_AMOUNT <= 0:
            raise ConfigurationError("MIN_ORDER_AMOUNT", "최소 주문 금액은 0보다 커야 합니다")
        if cls.FEE_RATE < 0 or cls.FEE_RATE > 0.01:
            raise ConfigurationError("FEE_RATE", "수수료율은 0과 0.01 사이여야 합니다")
        if cls.BUY_PERCENTAGE <= 0 or cls.BUY_PERCENTAGE > 1.0:
            raise ConfigurationError("BUY_PERCENTAGE", "매수 비율은 0과 1 사이여야 합니다")
        if cls.SELL_PERCENTAGE <= 0 or cls.SELL_PERCENTAGE > 1.0:
            raise ConfigurationError("SELL_PERCENTAGE", "매도 비율은 0과 1 사이여야 합니다")


class DataConfig:
    """데이터 수집 설정"""
    # 차트 데이터
    DAY_CHART_COUNT = get_env_int("DATA_DAY_CHART_COUNT", 60, min_value=1, max_value=200)  # RSI 다이버전스 분석을 위해 60일로 증가
    HOUR_CHART_COUNT = get_env_int("DATA_HOUR_CHART_COUNT", 24, min_value=1, max_value=200)
    MINUTE15_CHART_COUNT = get_env_int("DATA_MINUTE15_CHART_COUNT", 96, min_value=1, max_value=200)
    
    # 오더북
    ORDERBOOK_DEPTH = get_env_int("DATA_ORDERBOOK_DEPTH", 5, min_value=1, max_value=20)  # 상위 N개 호가 조회
    
    @classmethod
    def validate(cls):
        """데이터 설정 검증"""
        if cls.DAY_CHART_COUNT <= 0:
            raise ConfigurationError("DAY_CHART_COUNT", "일봉 조회 개수는 0보다 커야 합니다")
        if cls.ORDERBOOK_DEPTH <= 0:
            raise ConfigurationError("ORDERBOOK_DEPTH", "오더북 깊이는 0보다 커야 합니다")


class AIConfig:
    """AI 설정"""
    MODEL = get_env_str("AI_MODEL", "gpt-5.2")
    TEMPERATURE = get_env_float("AI_TEMPERATURE", 0.7, min_value=0.0, max_value=2.0)
    
    @classmethod
    def validate(cls):
        """AI 설정 검증"""
        # 최신 모델 포함: GPT-5.2, GPT-4o, GPT-4, GPT-3.5-turbo
        valid_models = [
            "gpt-5.2",           # 최신 모델 (2025년 12월 출시)
            "gpt-4o",            # GPT-4 Optimized
            "gpt-4o-2024-08-06", # GPT-4o 최신 버전
            "gpt-4",             # GPT-4
            "gpt-3.5-turbo",     # GPT-3.5 Turbo
            "o1-preview",        # O1 프리뷰 (추론 모델)
            "o1-mini"            # O1 미니 (추론 모델)
        ]
        if cls.MODEL not in valid_models:
            raise ConfigurationError("MODEL", f"지원하지 않는 모델입니다: {cls.MODEL}. 지원 모델: {', '.join(valid_models)}")
        if cls.TEMPERATURE < 0 or cls.TEMPERATURE > 2.0:
            raise ConfigurationError("TEMPERATURE", "Temperature는 0과 2 사이여야 합니다")


class APIConfig:
    """API 설정"""
    UPBIT_ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY")
    UPBIT_SECRET_KEY = os.getenv("UPBIT_SECRET_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    @classmethod
    def validate(cls):
        """API 키 검증"""
        if not cls.UPBIT_ACCESS_KEY or not cls.UPBIT_SECRET_KEY:
            raise ConfigurationError(
                "UPBIT_ACCESS_KEY",
                "UPBIT_ACCESS_KEY와 UPBIT_SECRET_KEY를 .env 파일에 설정해주세요."
            )
        if not cls.OPENAI_API_KEY:
            raise ConfigurationError(
                "OPENAI_API_KEY",
                "OPENAI_API_KEY를 .env 파일에 설정해주세요."
            )
    
    @classmethod
    def validate_upbit_only(cls):
        """Upbit API 키만 검증 (백테스팅 시 사용)"""
        if not cls.UPBIT_ACCESS_KEY or not cls.UPBIT_SECRET_KEY:
            raise ConfigurationError(
                "UPBIT_ACCESS_KEY",
                "UPBIT_ACCESS_KEY와 UPBIT_SECRET_KEY를 .env 파일에 설정해주세요."
            )


class StrategyConfig:
    """전략 설정 (ATR 기반 변동성 돌파)"""
    # ATR 설정
    ATR_PERIOD = get_env_int("STRATEGY_ATR_PERIOD", 14, min_value=5, max_value=50)

    # 동적 K값 설정 (변동성 구간별)
    K_VALUE_LOW_VOL = get_env_float("STRATEGY_K_VALUE_LOW_VOL", 2.0, min_value=0.5, max_value=5.0)  # ATR < 2%
    K_VALUE_MED_VOL = get_env_float("STRATEGY_K_VALUE_MED_VOL", 1.5, min_value=0.5, max_value=5.0)  # 2% <= ATR < 4%
    K_VALUE_HIGH_VOL = get_env_float("STRATEGY_K_VALUE_HIGH_VOL", 1.0, min_value=0.5, max_value=5.0)  # ATR >= 4%
    K_VALUE_DEFAULT = get_env_float("STRATEGY_K_VALUE_DEFAULT", 0.5, min_value=0.1, max_value=3.0)  # 고정 K값

    # 스탑로스/테이크프로핏 ATR 배수
    STOP_LOSS_ATR_MULTIPLIER = get_env_float("STRATEGY_STOP_LOSS_ATR_MULTIPLIER", 2.0, min_value=0.5, max_value=5.0)
    TAKE_PROFIT_ATR_MULTIPLIER = get_env_float("STRATEGY_TAKE_PROFIT_ATR_MULTIPLIER", 3.0, min_value=1.0, max_value=10.0)

    # 동적 K값 사용 여부
    USE_DYNAMIC_K = os.getenv("STRATEGY_USE_DYNAMIC_K", "false").lower() == "true"

    @classmethod
    def validate(cls):
        """전략 설정 검증"""
        if cls.ATR_PERIOD < 5:
            raise ConfigurationError("ATR_PERIOD", "ATR 기간은 최소 5 이상이어야 합니다")


class TrendFilterConfig:
    """트렌드 필터 설정"""
    # ADX 설정
    MIN_ADX = get_env_float("TREND_FILTER_MIN_ADX", 25.0, min_value=10.0, max_value=50.0)

    # 거래량 설정
    MIN_VOLUME_RATIO = get_env_float("TREND_FILTER_MIN_VOLUME_RATIO", 1.5, min_value=1.0, max_value=5.0)

    # 볼린저 밴드 설정
    MIN_BB_WIDTH_PCT = get_env_float("TREND_FILTER_MIN_BB_WIDTH_PCT", 4.0, min_value=1.0, max_value=20.0)
    BB_PERIOD = get_env_int("TREND_FILTER_BB_PERIOD", 20, min_value=10, max_value=50)

    @classmethod
    def validate(cls):
        """트렌드 필터 설정 검증"""
        if cls.MIN_ADX < 10:
            raise ConfigurationError("MIN_ADX", "최소 ADX는 10 이상이어야 합니다")
        if cls.MIN_VOLUME_RATIO < 1.0:
            raise ConfigurationError("MIN_VOLUME_RATIO", "거래량 비율은 1.0 이상이어야 합니다")


class SlippageConfig:
    """슬리피지 설정"""
    # 최대 허용 슬리피지
    MAX_SLIPPAGE_PCT = get_env_float("SLIPPAGE_MAX_PCT", 1.0, min_value=0.1, max_value=5.0)

    # 경고 슬리피지 임계값
    WARNING_SLIPPAGE_PCT = get_env_float("SLIPPAGE_WARNING_PCT", 0.3, min_value=0.1, max_value=2.0)

    # 백테스팅 기본 슬리피지
    BACKTEST_DEFAULT_SLIPPAGE = get_env_float("SLIPPAGE_BACKTEST_DEFAULT", 0.001, min_value=0.0, max_value=0.01)

    # 분할 주문 임계값 (이 금액 이상이면 분할 주문 권장)
    SPLIT_ORDER_THRESHOLD_KRW = get_env_int("SLIPPAGE_SPLIT_THRESHOLD", 5000000, min_value=1000000)  # 500만원

    @classmethod
    def validate(cls):
        """슬리피지 설정 검증"""
        if cls.MAX_SLIPPAGE_PCT < cls.WARNING_SLIPPAGE_PCT:
            raise ConfigurationError("MAX_SLIPPAGE_PCT", "최대 슬리피지는 경고 슬리피지보다 커야 합니다")


class ScannerConfig:
    """
    멀티코인 스캐닝 설정

    ⚠️ 중요: 이 값을 변경할 때 반드시 아래 문서들도 함께 업데이트하세요:
    - docs/guide/ARCHITECTURE.md
    - docs/diagrams/08-multi-coin-scanning.mmd
    - main.py, trading_pipeline.py docstrings
    - 관련 테스트 파일 (test_coin_scan_stage.py, test_scanner_coin_selector.py)

    변경 시 grep으로 모든 참조를 확인하세요:
    $ grep -r "liquidity_top_n\|20개\|10개" --include="*.py" --include="*.md" --include="*.mmd"
    """
    # 유동성 스캔 상위 N개 코인
    LIQUIDITY_TOP_N = get_env_int("SCANNER_LIQUIDITY_TOP_N", 10, min_value=5, max_value=50)

    # 최소 거래대금 (원)
    MIN_VOLUME_KRW = get_env_int("SCANNER_MIN_VOLUME_KRW", 10_000_000_000, min_value=1_000_000_000)  # 100억원

    # 백테스팅 통과 상위 N개
    BACKTEST_TOP_N = get_env_int("SCANNER_BACKTEST_TOP_N", 5, min_value=1, max_value=20)

    # 최종 선택 N개
    FINAL_SELECT_N = get_env_int("SCANNER_FINAL_SELECT_N", 2, min_value=1, max_value=10)

    # 섹터 분산 설정
    ENABLE_SECTOR_DIVERSIFICATION = os.getenv("SCANNER_ENABLE_SECTOR_DIVERSIFICATION", "true").lower() == "true"
    ONE_PER_SECTOR = os.getenv("SCANNER_ONE_PER_SECTOR", "true").lower() == "true"
    EXCLUDE_UNKNOWN_SECTOR = os.getenv("SCANNER_EXCLUDE_UNKNOWN_SECTOR", "false").lower() == "true"

    @classmethod
    def validate(cls):
        """스캐너 설정 검증"""
        if cls.LIQUIDITY_TOP_N < cls.BACKTEST_TOP_N:
            raise ConfigurationError(
                "LIQUIDITY_TOP_N",
                f"유동성 스캔 개수({cls.LIQUIDITY_TOP_N})는 백테스팅 통과 개수({cls.BACKTEST_TOP_N})보다 커야 합니다"
            )
        if cls.BACKTEST_TOP_N < cls.FINAL_SELECT_N:
            raise ConfigurationError(
                "BACKTEST_TOP_N",
                f"백테스팅 통과 개수({cls.BACKTEST_TOP_N})는 최종 선택 개수({cls.FINAL_SELECT_N})보다 커야 합니다"
            )


# 설정 초기화 시 검증
def validate_all_configs():
    """모든 설정 검증"""
    TradingConfig.validate()
    DataConfig.validate()
    AIConfig.validate()
    APIConfig.validate()
    StrategyConfig.validate()
    TrendFilterConfig.validate()
    SlippageConfig.validate()
    ScannerConfig.validate()

