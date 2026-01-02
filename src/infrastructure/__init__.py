"""
Infrastructure Layer - External System Adapters

This module contains adapters that implement the application ports,
handling communication with external systems like exchanges, AI services,
databases, and market data providers.

Structure:
- adapters/exchange/: Exchange API adapters (Upbit, etc.)
- adapters/ai/: AI service adapters (OpenAI, etc.)
- adapters/market_data/: Market data adapters
- adapters/persistence/: Database adapters (PostgreSQL, in-memory)
"""
from src.infrastructure.adapters.exchange.upbit_adapter import UpbitExchangeAdapter
from src.infrastructure.adapters.ai.openai_adapter import OpenAIAdapter
from src.infrastructure.adapters.market_data.upbit_data_adapter import UpbitMarketDataAdapter
from src.infrastructure.adapters.persistence.memory_adapter import InMemoryPersistenceAdapter

__all__ = [
    "UpbitExchangeAdapter",
    "OpenAIAdapter",
    "UpbitMarketDataAdapter",
    "InMemoryPersistenceAdapter",
]
