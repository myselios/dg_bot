# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Bitcoin AI automated trading bot that uses OpenAI GPT-4 for trading decisions. The system runs on a 1-hour interval schedule using APScheduler, executing trades on the Upbit exchange based on AI analysis of technical indicators and market data.

**Tech Stack**: Python 3.11, FastAPI, PostgreSQL, Docker, APScheduler, OpenAI GPT-4, TA-Lib

## Common Commands

### Environment Setup
```bash
# Activate virtual environment (venv)
# Windows PowerShell
.\venv\Scripts\Activate.ps1

# Windows CMD
venv\Scripts\activate.bat

# Linux/Mac
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-api.txt
```

### Testing
```bash
# Run all tests (must be in venv)
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_module_name.py -v

# Run tests with coverage
python -m pytest tests/ --cov=src --cov=backend --cov-report=html

# Run only unit tests
python -m pytest tests/ -m unit -v

# Run only integration tests
python -m pytest tests/ -m integration -v

# Run scheduler tests
python -m pytest tests/backend/app/core/test_scheduler.py -v

# Run a single test
python -m pytest tests/test_module.py::TestClass::test_method -v
```

### Running the Bot

```bash
# Run trading cycle once (development)
python main.py

# Run scheduler (1-hour interval automated trading)
python scheduler_main.py

# Run with Docker (scheduler only)
docker-compose up -d scheduler
docker-compose logs -f scheduler

# Run full stack (DB, API, monitoring)
docker-compose -f docker-compose.full-stack.yml up -d
```

### Docker Operations
```bash
# Build and run scheduler
docker-compose build scheduler
docker-compose up -d scheduler

# View logs
docker-compose logs -f scheduler

# Stop services
docker-compose down

# Clean rebuild
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

### Database Operations
```bash
# The database is managed by Docker Compose
# PostgreSQL runs in a container with persistent volume
# Tables are auto-created via SQLAlchemy on first run

# Access PostgreSQL container
docker exec -it dg_bot-postgres-1 psql -U postgres -d trading_bot
```

## Architecture

### System Flow

The bot operates on a **dual-mode architecture**:

1. **Standalone Mode** (`main.py`): Single execution of trading cycle
2. **Scheduler Mode** (`scheduler_main.py`): Automated 1-hour interval execution

**Key Flow**:
```
scheduler_main.py
  → backend/app/core/scheduler.py (APScheduler configuration)
    → trading_job() calls main.execute_trading_cycle()
      → QuickBacktestFilter (rule-based filtering, no AI)
      → SignalAnalyzer (technical analysis)
      → AIService (GPT-4 decision making)
      → TradingService (order execution)
      → Database recording (via backend models)
      → Telegram notifications
```

### Directory Structure

```
dg_bot/
├── main.py                    # Main trading cycle (standalone execution)
├── scheduler_main.py          # Scheduler entry point (automated mode)
├── src/                       # Core trading logic
│   ├── ai/                    # AI decision making (GPT-4)
│   │   ├── service.py         # AIService - main AI analysis
│   │   └── market_correlation.py
│   ├── api/                   # Exchange API clients
│   │   └── upbit_client.py    # Upbit exchange integration
│   ├── backtesting/           # Backtesting engine
│   │   ├── backtester.py      # Main backtesting engine
│   │   ├── quick_filter.py    # Fast rule-based filtering
│   │   ├── rule_based_strategy.py  # Rule-based strategy
│   │   └── ai_strategy.py     # AI-based strategy
│   ├── data/                  # Data collection
│   │   └── collector.py       # Market data collector
│   ├── trading/               # Trading execution
│   │   ├── service.py         # TradingService - order execution
│   │   ├── indicators.py      # Technical indicators (RSI, MACD, etc.)
│   │   └── signal_analyzer.py # Signal analysis
│   ├── position/              # Position management
│   └── config/                # Configuration
│       └── settings.py        # All configuration classes
├── backend/                   # FastAPI backend + database
│   ├── app/
│   │   ├── main.py           # FastAPI application entry
│   │   ├── api/v1/           # REST API endpoints
│   │   │   └── endpoints/
│   │   │       ├── bot_control.py  # Bot control API
│   │   │       └── trades.py       # Trade history API
│   │   ├── core/
│   │   │   ├── config.py     # Backend settings
│   │   │   └── scheduler.py  # APScheduler configuration
│   │   ├── db/               # Database setup
│   │   │   ├── base.py       # SQLAlchemy base
│   │   │   ├── session.py    # DB session management
│   │   │   └── init_db.py    # DB initialization
│   │   ├── models/           # SQLAlchemy ORM models
│   │   │   ├── trade.py      # Trade records
│   │   │   ├── ai_decision.py # AI decision logs
│   │   │   ├── order.py      # Order records
│   │   │   ├── portfolio.py  # Portfolio snapshots
│   │   │   ├── bot_config.py # Bot configuration
│   │   │   └── system_log.py # System logs
│   │   ├── schemas/          # Pydantic schemas
│   │   └── services/
│   │       ├── trading_engine.py  # Trading logic integration
│   │       ├── notification.py    # Telegram notifications
│   │       └── metrics.py         # Prometheus metrics
│   └── tests/                # Backend tests
├── tests/                    # Main tests directory
├── scripts/backtesting/      # Data collection scripts
├── monitoring/               # Prometheus + Grafana configs
└── docs/                     # Documentation (ALL .md files go here)
```

### Key Components

**AIService** (`src/ai/service.py`):
- Uses OpenAI GPT-4 for trading decisions
- Analyzes technical indicators, market trends, and chart patterns
- Returns decision with confidence score and reasoning
- Methods: `analyze()`, `prepare_analysis_data()`

**TradingService** (`src/trading/service.py`):
- Executes buy/sell orders via Upbit API
- Handles fee calculation, slippage, split orders
- Methods: `buy()`, `sell()`, `calculate_fee()`, `calculate_slippage()`

**QuickBacktestFilter** (`src/backtesting/quick_filter.py`):
- Fast rule-based filtering WITHOUT AI calls
- Uses rule-based strategy to pre-filter trading opportunities
- Significantly reduces AI API costs

**Scheduler** (`backend/app/core/scheduler.py`):
- APScheduler configuration for 1-hour interval jobs
- `trading_job()`: Main scheduled task
- Handles error recovery, duplicate prevention (max_instances=1)

**Database Models** (`backend/app/models/`):
- `Trade`: Executed trades
- `AIDecision`: AI analysis logs
- `Order`: Order details
- `Portfolio`: Portfolio snapshots
- All use SQLAlchemy ORM with async sessions

### Data Flow

1. **Data Collection**: `DataCollector` fetches OHLCV data from Upbit
2. **Technical Analysis**: `TechnicalIndicators` calculates RSI, MACD, Bollinger Bands
3. **Quick Filter**: `QuickBacktestFilter` applies rule-based strategy (no AI cost)
4. **Signal Analysis**: `SignalAnalyzer` analyzes buy/sell signals
5. **AI Decision**: `AIService` makes final decision via GPT-4
6. **Order Execution**: `TradingService` executes trade on Upbit
7. **Database Recording**: Models store trade, decision, and portfolio data
8. **Notifications**: Telegram alerts sent via `notification.py`
9. **Metrics**: Prometheus metrics recorded via `metrics.py`

## Development Guidelines

### TDD (Test-Driven Development)

This project strictly follows TDD principles (see `.cursorrules`):

1. **Red**: Write failing test first
2. **Green**: Write minimal code to pass test
3. **Refactor**: Optimize code while keeping tests green

**Test Structure**:
- All tests in `tests/` directory
- Use `@pytest.mark.unit` for unit tests
- Use `@pytest.mark.integration` for integration tests
- Fixtures in `conftest.py`
- Follow Given-When-Then pattern

### Virtual Environment (venv)

**CRITICAL**: Always use venv for Python commands
- Location: `venv/` (project root)
- Activate before running any Python commands
- Never run Python commands outside venv

### File Organization Rules

From `.cursorrules`:

1. **Documentation**: ALL `.md` files MUST go in `docs/` (except root `README.md`)
2. **Reports**: Analysis/performance reports go in `docs/reports/`
3. **Scripts**: Development scripts in project root, data scripts in `scripts/`
4. **Temporary Files**: Delete temporary test scripts after use

### Windows Encoding (PowerShell)

If running on Windows, PowerShell scripts need UTF-8 encoding setup:

```powershell
# Add to start of .ps1 files
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
```

Prefer `.bat` files over `.ps1` for Windows scripts when possible.

## Configuration

### Environment Variables

All configuration is in `.env` file (copy from `env.example`):

**Required**:
- `UPBIT_ACCESS_KEY`: Upbit API access key
- `UPBIT_SECRET_KEY`: Upbit API secret key
- `OPENAI_API_KEY`: OpenAI API key

**Optional but Recommended**:
- `TELEGRAM_BOT_TOKEN`: Telegram bot token
- `TELEGRAM_CHAT_ID`: Telegram chat ID
- `SENTRY_DSN`: Sentry error tracking DSN
- `POSTGRES_*`: Database configuration (for Docker)
- `PROMETHEUS_ENABLED`: Enable Prometheus metrics
- `GRAFANA_*`: Grafana configuration

### Configuration Classes

All in `src/config/settings.py`:
- `TradingConfig`: Trading parameters (fee rate, min trade, etc.)
- `AIConfig`: AI model settings (GPT-4, temperature, etc.)
- `DataConfig`: Data collection settings (intervals, counts)
- `BacktestConfig`: Backtesting parameters
- Backend config in `backend/app/core/config.py`

## Important Notes

### Trading Safety

1. **Start Small**: Test with minimal amounts first
2. **Monitor Closely**: Check logs and Telegram notifications
3. **API Key Security**: NEVER commit `.env` file
4. **Dry Run**: Use backtesting (`python backtest.py`) before live trading

### Scheduler Behavior

- Runs every 1 hour (configurable in `scheduler.py`)
- `max_instances=1` prevents concurrent executions
- Graceful shutdown on SIGINT/SIGTERM
- Auto-recovery on errors (logs to Sentry if enabled)

### Database

- PostgreSQL required for production (via Docker)
- Tables auto-created on first run via SQLAlchemy
- Async sessions throughout backend
- Migrations not implemented (using declarative_base auto-create)

### AI Costs

- Each AI decision call costs money (GPT-4 API)
- `QuickBacktestFilter` reduces AI calls by pre-filtering with rules
- Monitor usage via OpenAI dashboard

### Backtesting

Two modes:
1. **Rule-based only**: No AI calls, fast and free
2. **AI-based**: Includes GPT-4 analysis, slower and costly

Use `scripts/backtesting/` for historical data collection.

## Common Issues

### Import Errors
- Ensure venv is activated
- Check `PYTHONPATH` includes project root
- `scheduler_main.py` adds project root to `sys.path`

### Database Connection
- Verify PostgreSQL is running (`docker-compose ps`)
- Check `DATABASE_URL` in `.env`
- Ensure async driver: `postgresql+asyncpg://...`

### API Errors
- Verify API keys in `.env`
- Check Upbit/OpenAI rate limits
- Review logs in `logs/` directory

### Scheduler Not Running
- Check `scheduler.log` in `logs/scheduler/`
- Verify no other instance is running
- Check system time (scheduler uses Asia/Seoul timezone)

## Useful References

- [User Guide](docs/USER_GUIDE.md): Complete user documentation
- [Scheduler Guide](docs/SCHEDULER_GUIDE.md): Scheduler detailed guide
- [Docker Guide](docs/DOCKER_GUIDE.md): Docker setup and deployment
- [Architecture](docs/ARCHITECTURE.md): System architecture details
- [Trading Flow](docs/TRADING_SEQUENCE_FLOW.md): Complete trading sequence
