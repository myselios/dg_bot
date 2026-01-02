"""
TradingRunner - Main entry point for trading cycles.

This module provides the TradingRunner class that orchestrates
trading cycles using the application use cases.
"""
import re
from decimal import Decimal
from typing import Dict, Any, Optional

from src.container import Container
from src.application.dto.analysis import DecisionType
from src.domain.value_objects.money import Money, Currency


# Valid ticker pattern
TICKER_PATTERN = re.compile(r"^KRW-[A-Z]{2,10}$")


class TradingRunner:
    """
    Orchestrates trading cycles using application use cases.

    This is the main entry point for both CLI and scheduler execution.
    It coordinates market analysis and trade execution through the DI container.
    """

    def __init__(
        self,
        container: Container,
        buy_amount_krw: Optional[Decimal] = None,
        dry_run: bool = False,
    ):
        """
        Initialize TradingRunner.

        Args:
            container: DI container with wired dependencies
            buy_amount_krw: Amount to buy in KRW (default 100,000)
            dry_run: If True, simulate trades without execution
        """
        self.container = container
        self.buy_amount_krw = buy_amount_krw or Decimal("100000")
        self.dry_run = dry_run

        # Get use cases from container
        self._analyze_market = container.get_analyze_market_use_case()
        self._execute_trade = container.get_execute_trade_use_case()
        self._manage_position = container.get_manage_position_use_case()

    async def execute(self, ticker: str) -> Dict[str, Any]:
        """
        Execute a trading cycle for a given ticker.

        Args:
            ticker: Trading pair (e.g., "KRW-BTC")

        Returns:
            Result dict with status, decision, and execution details
        """
        # Validate ticker
        if not self._validate_ticker(ticker):
            return {
                "status": "failed",
                "decision": "hold",
                "error": f"Invalid ticker format: {ticker}",
                "dry_run": self.dry_run,
            }

        try:
            # Check current position
            position = await self._manage_position.get_position(ticker)
            has_position = position is not None

            if has_position:
                # Analyze exit opportunity
                return await self._analyze_exit(ticker, position)
            else:
                # Analyze entry opportunity
                return await self._analyze_entry(ticker)

        except Exception as e:
            return {
                "status": "failed",
                "decision": "hold",
                "error": str(e),
                "dry_run": self.dry_run,
            }

    async def _analyze_entry(self, ticker: str) -> Dict[str, Any]:
        """
        Analyze entry opportunity for a ticker.

        Args:
            ticker: Trading pair

        Returns:
            Result dict
        """
        try:
            # Get AI analysis
            decision = await self._analyze_market.analyze_entry(ticker)

            result = {
                "status": "completed",
                "decision": decision.decision.value if hasattr(decision.decision, 'value') else str(decision.decision),
                "confidence": float(decision.confidence),
                "reasoning": decision.reasoning,
                "dry_run": self.dry_run,
            }

            # Execute trade if BUY decision
            if decision.decision == DecisionType.BUY:
                if self.dry_run:
                    result["status"] = "dry_run"
                    result["would_execute"] = "buy"
                    result["amount"] = float(self.buy_amount_krw)
                else:
                    exec_result = await self._execute_buy(ticker)
                    result.update(exec_result)

            return result

        except Exception as e:
            return {
                "status": "failed",
                "decision": "hold",
                "error": str(e),
                "dry_run": self.dry_run,
            }

    async def _analyze_exit(
        self,
        ticker: str,
        position: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Analyze exit opportunity for an existing position.

        Args:
            ticker: Trading pair
            position: Current position info

        Returns:
            Result dict
        """
        try:
            # Get AI analysis for exit
            decision = await self._analyze_market.analyze_exit(ticker, position)

            result = {
                "status": "completed",
                "decision": decision.decision.value if hasattr(decision.decision, 'value') else str(decision.decision),
                "confidence": float(decision.confidence),
                "reasoning": decision.reasoning,
                "position": position,
                "dry_run": self.dry_run,
            }

            # Execute trade if SELL decision
            if decision.decision == DecisionType.SELL:
                if self.dry_run:
                    result["status"] = "dry_run"
                    result["would_execute"] = "sell"
                    result["volume"] = float(position.get("volume", 0))
                else:
                    exec_result = await self._execute_sell(ticker, position)
                    result.update(exec_result)

            return result

        except Exception as e:
            return {
                "status": "failed",
                "decision": "hold",
                "error": str(e),
                "dry_run": self.dry_run,
            }

    async def _execute_buy(self, ticker: str) -> Dict[str, Any]:
        """
        Execute a buy order.

        Args:
            ticker: Trading pair

        Returns:
            Execution result
        """
        try:
            amount = Money.krw(self.buy_amount_krw)
            response = await self._execute_trade.execute_buy(ticker, amount)

            if response.success:
                return {
                    "status": "executed",
                    "trade_type": "buy",
                    "order_id": response.order_id,
                    "executed_price": float(response.executed_price.amount) if response.executed_price else None,
                    "executed_volume": float(response.executed_volume) if response.executed_volume else None,
                    "fee": float(response.fee.amount) if response.fee else None,
                }
            else:
                return {
                    "status": "failed",
                    "trade_type": "buy",
                    "error": response.error_message,
                }

        except Exception as e:
            return {
                "status": "failed",
                "trade_type": "buy",
                "error": str(e),
            }

    async def _execute_sell(
        self,
        ticker: str,
        position: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a sell order.

        Args:
            ticker: Trading pair
            position: Current position info

        Returns:
            Execution result
        """
        try:
            volume = Decimal(str(position.get("volume", 0)))

            if volume <= 0:
                return {
                    "status": "failed",
                    "trade_type": "sell",
                    "error": "No volume to sell",
                }

            response = await self._execute_trade.execute_sell(ticker, volume)

            if response.success:
                return {
                    "status": "executed",
                    "trade_type": "sell",
                    "order_id": response.order_id,
                    "executed_price": float(response.executed_price.amount) if response.executed_price else None,
                    "executed_volume": float(response.executed_volume) if response.executed_volume else None,
                    "fee": float(response.fee.amount) if response.fee else None,
                }
            else:
                return {
                    "status": "failed",
                    "trade_type": "sell",
                    "error": response.error_message,
                }

        except Exception as e:
            return {
                "status": "failed",
                "trade_type": "sell",
                "error": str(e),
            }

    def _validate_ticker(self, ticker: str) -> bool:
        """Validate ticker format."""
        return bool(TICKER_PATTERN.match(ticker))
