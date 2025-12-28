"""
Prometheus 메트릭 서비스
애플리케이션 성능 및 비즈니스 메트릭을 수집합니다.
"""
import logging
from prometheus_client import Counter, Histogram, Gauge, Info
from prometheus_client import make_asgi_app

logger = logging.getLogger(__name__)

# 애플리케이션 정보
app_info = Info('trading_bot_info', 'Trading Bot Information')
app_info.info({
    'version': '1.0.0',
    'name': 'Bitcoin Trading Bot'
})

# HTTP 요청 메트릭
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

# 트레이딩 메트릭
trades_total = Counter(
    'trades_total',
    'Total number of trades',
    ['symbol', 'side']
)

trade_volume_krw = Counter(
    'trade_volume_krw_total',
    'Total trade volume in KRW',
    ['symbol', 'side']
)

trade_fee_krw = Counter(
    'trade_fee_krw_total',
    'Total trade fees in KRW',
    ['symbol']
)

# AI 판단 메트릭
ai_decisions_total = Counter(
    'ai_decisions_total',
    'Total AI decisions',
    ['symbol', 'decision']
)

ai_confidence = Histogram(
    'ai_confidence',
    'AI decision confidence',
    ['symbol', 'decision']
)

# 포트폴리오 메트릭
portfolio_value_krw = Gauge(
    'portfolio_value_krw',
    'Current portfolio value in KRW'
)

portfolio_profit_rate = Gauge(
    'portfolio_profit_rate',
    'Portfolio profit rate percentage'
)

# 봇 상태 메트릭
bot_running = Gauge(
    'bot_running',
    'Bot running status (1=running, 0=stopped)'
)

bot_errors_total = Counter(
    'bot_errors_total',
    'Total bot errors',
    ['error_type']
)

# 스케줄러 메트릭
scheduler_job_duration_seconds = Histogram(
    'scheduler_job_duration_seconds',
    'Scheduler job duration in seconds',
    ['job_name']
)

scheduler_job_success_total = Counter(
    'scheduler_job_success_total',
    'Total successful scheduler jobs',
    ['job_name']
)

scheduler_job_failure_total = Counter(
    'scheduler_job_failure_total',
    'Total failed scheduler jobs',
    ['job_name']
)


def record_trade(symbol: str, side: str, volume: float, fee: float):
    """거래 메트릭 기록"""
    trades_total.labels(symbol=symbol, side=side).inc()
    trade_volume_krw.labels(symbol=symbol, side=side).inc(volume)
    trade_fee_krw.labels(symbol=symbol).inc(fee)


def record_ai_decision(symbol: str, decision: str, confidence: float):
    """AI 판단 메트릭 기록"""
    ai_decisions_total.labels(symbol=symbol, decision=decision).inc()
    ai_confidence.labels(symbol=symbol, decision=decision).observe(confidence)


def record_portfolio_value(value_krw: float, profit_rate: float):
    """포트폴리오 메트릭 기록"""
    portfolio_value_krw.set(value_krw)
    portfolio_profit_rate.set(profit_rate)


def record_bot_error(error_type: str):
    """봇 에러 메트릭 기록"""
    bot_errors_total.labels(error_type=error_type).inc()


def set_bot_running(is_running: bool):
    """봇 실행 상태 설정"""
    bot_running.set(1 if is_running else 0)


# ASGI 애플리케이션 (FastAPI에 마운트)
metrics_app = make_asgi_app()



