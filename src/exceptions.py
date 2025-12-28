"""
트레이딩 시스템 예외 클래스
"""
from typing import Optional


class TradingError(Exception):
    """트레이딩 관련 기본 예외"""
    
    def __init__(self, message: str, error_code: Optional[str] = None):
        """
        Args:
            message: 에러 메시지
            error_code: 에러 코드 (선택사항)
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class InsufficientFundsError(TradingError):
    """잔고 부족 예외"""
    
    def __init__(self, required: float, available: float, currency: str = "KRW"):
        """
        Args:
            required: 필요한 금액
            available: 사용 가능한 금액
            currency: 통화
        """
        message = (
            f"잔고 부족: {currency} {required:,.0f}원이 필요하지만 "
            f"{available:,.0f}원만 사용 가능합니다."
        )
        super().__init__(message, error_code="INSUFFICIENT_FUNDS")
        self.required = required
        self.available = available
        self.currency = currency


class OrderExecutionError(TradingError):
    """주문 실행 실패 예외"""
    
    def __init__(self, ticker: str, order_type: str, reason: str):
        """
        Args:
            ticker: 거래 종목
            order_type: 주문 유형 ('buy' 또는 'sell')
            reason: 실패 이유
        """
        message = f"{order_type.upper()} 주문 실패 ({ticker}): {reason}"
        super().__init__(message, error_code="ORDER_EXECUTION_FAILED")
        self.ticker = ticker
        self.order_type = order_type
        self.reason = reason


class DataCollectionError(TradingError):
    """데이터 수집 실패 예외"""
    
    def __init__(self, source: str, reason: str):
        """
        Args:
            source: 데이터 소스 (예: 'Upbit API', 'Cache')
            reason: 실패 이유
        """
        message = f"데이터 수집 실패 ({source}): {reason}"
        super().__init__(message, error_code="DATA_COLLECTION_FAILED")
        self.source = source
        self.reason = reason


class ConfigurationError(TradingError):
    """설정 오류 예외"""
    
    def __init__(self, config_key: str, reason: str):
        """
        Args:
            config_key: 설정 키
            reason: 오류 이유
        """
        message = f"설정 오류 ({config_key}): {reason}"
        super().__init__(message, error_code="CONFIGURATION_ERROR")
        self.config_key = config_key
        self.reason = reason


class APIError(TradingError):
    """API 호출 실패 예외"""
    
    def __init__(self, api_name: str, status_code: Optional[int] = None, reason: str = ""):
        """
        Args:
            api_name: API 이름
            status_code: HTTP 상태 코드 (선택사항)
            reason: 실패 이유
        """
        if status_code:
            message = f"API 호출 실패 ({api_name}): HTTP {status_code} - {reason}"
        else:
            message = f"API 호출 실패 ({api_name}): {reason}"
        super().__init__(message, error_code="API_ERROR")
        self.api_name = api_name
        self.status_code = status_code
        self.reason = reason


class AuthenticationError(APIError):
    """인증 실패 예외"""
    
    def __init__(self, api_name: str, reason: str = "인증 정보가 유효하지 않습니다"):
        """
        Args:
            api_name: API 이름
            reason: 실패 이유
        """
        super().__init__(api_name, status_code=401, reason=reason)
        self.error_code = "AUTHENTICATION_FAILED"


class RateLimitError(APIError):
    """API 레이트 리밋 초과 예외"""
    
    def __init__(self, api_name: str, retry_after: Optional[int] = None):
        """
        Args:
            api_name: API 이름
            retry_after: 재시도까지 대기 시간(초) (선택사항)
        """
        if retry_after:
            message = f"API 레이트 리밋 초과 ({api_name}): {retry_after}초 후 재시도 가능"
        else:
            message = f"API 레이트 리밋 초과 ({api_name})"
        super().__init__(api_name, status_code=429, reason=message)
        self.error_code = "RATE_LIMIT_EXCEEDED"
        self.retry_after = retry_after




