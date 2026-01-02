"""
ManagePositionUseCase - Business logic for position management.

This use case handles position tracking, P&L calculation,
and stop loss / take profit evaluation.
"""
from decimal import Decimal
from typing import Optional, Dict, Any, List
import re

from src.application.ports.outbound.exchange_port import ExchangePort
from src.application.ports.outbound.persistence_port import PersistencePort
from src.domain.entities.trade import Trade, Position, OrderSide
from src.domain.value_objects.money import Money, Currency
from src.domain.value_objects.percentage import Percentage


# Ticker format pattern
TICKER_PATTERN = re.compile(r"^KRW-[A-Z]{2,10}$")


class ManagePositionUseCase:
    """
    Use case for position management.

    Handles position tracking, P&L calculation, and exit signal evaluation.
    """

    def __init__(
        self,
        exchange: ExchangePort,
        persistence: PersistencePort,
    ):
        """
        Initialize with required ports.

        Args:
            exchange: Exchange port for position data
            persistence: Persistence port for position storage
        """
        self.exchange = exchange
        self.persistence = persistence

    async def get_position(
        self,
        ticker: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get current position for a ticker.

        Args:
            ticker: Trading pair

        Returns:
            Position info dict or None if no position
        """
        if not self._validate_ticker(ticker):
            return None

        try:
            position = await self.exchange.get_position(ticker)
            if position is None:
                return None

            current_price = await self.exchange.get_current_price(ticker)

            # Calculate derived values - try different attribute names
            avg_price = self._get_avg_price(position)

            current_value = current_price.amount * position.volume
            total_cost = avg_price * position.volume
            unrealized_pnl = current_value - total_cost
            profit_rate = ((current_price.amount - avg_price) / avg_price * 100) if avg_price > 0 else Decimal("0")

            return {
                "ticker": ticker,
                "volume": position.volume,
                "avg_buy_price": avg_price,
                "current_price": current_price.amount,
                "current_value": current_value,
                "total_cost": total_cost,
                "unrealized_pnl": unrealized_pnl,
                "profit_rate": profit_rate,
            }
        except Exception:
            return None

    async def calculate_pnl(
        self,
        ticker: str,
    ) -> Dict[str, Decimal]:
        """
        Calculate unrealized P&L for a position.

        Args:
            ticker: Trading pair

        Returns:
            Dict with pnl values
        """
        if not self._validate_ticker(ticker):
            return {"unrealized_pnl": Decimal("0"), "profit_rate": Decimal("0")}

        position = await self.exchange.get_position(ticker)
        if position is None:
            return {"unrealized_pnl": Decimal("0"), "profit_rate": Decimal("0")}

        try:
            current_price = await self.exchange.get_current_price(ticker)

            avg_price = self._get_avg_price(position)

            unrealized_pnl = (current_price.amount - avg_price) * position.volume
            profit_rate = ((current_price.amount - avg_price) / avg_price * 100) if avg_price > 0 else Decimal("0")

            return {
                "unrealized_pnl": unrealized_pnl,
                "profit_rate": profit_rate,
            }
        except Exception:
            return {"unrealized_pnl": Decimal("0"), "profit_rate": Decimal("0")}

    async def should_stop_loss(
        self,
        ticker: str,
        stop_loss_pct: Percentage,
    ) -> bool:
        """
        Check if stop loss should be triggered.

        Args:
            ticker: Trading pair
            stop_loss_pct: Stop loss threshold (should be negative, e.g., -5%)

        Returns:
            True if stop loss should trigger
        """
        if not self._validate_ticker(ticker):
            return False

        # Stop loss should be negative
        if stop_loss_pct.value >= 0:
            return False

        try:
            pnl = await self.calculate_pnl(ticker)
            profit_rate_decimal = pnl["profit_rate"] / 100  # Convert to decimal

            # Stop loss triggers when profit rate <= threshold
            return profit_rate_decimal <= stop_loss_pct.value
        except Exception:
            return False

    async def should_take_profit(
        self,
        ticker: str,
        take_profit_pct: Percentage,
    ) -> bool:
        """
        Check if take profit should be triggered.

        Args:
            ticker: Trading pair
            take_profit_pct: Take profit threshold (should be positive, e.g., +10%)

        Returns:
            True if take profit should trigger
        """
        if not self._validate_ticker(ticker):
            return False

        # Take profit should be positive
        if take_profit_pct.value <= 0:
            return False

        try:
            pnl = await self.calculate_pnl(ticker)
            profit_rate_decimal = pnl["profit_rate"] / 100  # Convert to decimal

            # Take profit triggers when profit rate >= threshold
            return profit_rate_decimal >= take_profit_pct.value
        except Exception:
            return False

    async def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Get summary of all positions.

        Returns:
            Portfolio summary with all positions
        """
        try:
            positions = await self.exchange.get_all_positions()

            if not positions:
                return {
                    "positions": [],
                    "total_value": Decimal("0"),
                    "total_cost": Decimal("0"),
                    "total_pnl": Decimal("0"),
                }

            position_summaries = []
            total_value = Decimal("0")
            total_cost = Decimal("0")

            for pos in positions:
                ticker = pos.ticker

                # Get avg price
                avg_price = Decimal("0")
                if hasattr(pos, 'avg_buy_price'):
                    avg_price = pos.avg_buy_price.amount
                elif hasattr(pos, 'avg_entry_price'):
                    avg_price = pos.avg_entry_price.amount

                # Get current price
                current_price = Decimal("0")
                if hasattr(pos, 'current_price'):
                    current_price = pos.current_price.amount
                else:
                    try:
                        price_money = await self.exchange.get_current_price(ticker)
                        current_price = price_money.amount
                    except Exception:
                        pass

                value = current_price * pos.volume
                cost = avg_price * pos.volume
                pnl = value - cost
                profit_rate = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else Decimal("0")

                position_summaries.append({
                    "ticker": ticker,
                    "volume": pos.volume,
                    "avg_buy_price": avg_price,
                    "current_price": current_price,
                    "value": value,
                    "cost": cost,
                    "pnl": pnl,
                    "profit_rate": profit_rate,
                })

                total_value += value
                total_cost += cost

            return {
                "positions": position_summaries,
                "total_value": total_value,
                "total_cost": total_cost,
                "total_pnl": total_value - total_cost,
            }
        except Exception:
            return {
                "positions": [],
                "total_value": Decimal("0"),
                "total_cost": Decimal("0"),
                "total_pnl": Decimal("0"),
            }

    async def update_position_from_trade(
        self,
        trade: Trade,
    ) -> Optional[Position]:
        """
        Update position after a trade is executed.

        Args:
            trade: Completed trade

        Returns:
            Updated position or None
        """
        try:
            ticker = trade.ticker
            symbol = ticker.split("-")[-1] if "-" in ticker else ticker

            # Get existing position
            existing = await self.persistence.get_position(ticker)

            if trade.side == OrderSide.BUY:
                if existing is None:
                    # Create new position
                    new_position = Position.create(
                        ticker=ticker,
                        symbol=symbol,
                        volume=trade.volume,
                        avg_entry_price=trade.price,
                    )
                else:
                    # Add to existing position
                    new_position = existing.add(trade.volume, trade.price)

                await self.persistence.save_position(new_position)
                return new_position

            else:  # SELL
                if existing is None:
                    return None

                if trade.volume >= existing.volume:
                    # Close entire position
                    await self.persistence.close_position(ticker)
                    return existing.close()
                else:
                    # Reduce position
                    new_position = existing.reduce(trade.volume)
                    await self.persistence.save_position(new_position)
                    return new_position

        except Exception:
            return None

    def _validate_ticker(self, ticker: str) -> bool:
        """Validate ticker format."""
        return bool(TICKER_PATTERN.match(ticker))

    def _get_avg_price(self, position) -> Decimal:
        """
        Extract average price from position object.

        Handles different attribute names (avg_buy_price, avg_entry_price).
        """
        try:
            # Try avg_buy_price first (DTO style)
            if hasattr(position, 'avg_buy_price') and position.avg_buy_price is not None:
                price = position.avg_buy_price
                if hasattr(price, 'amount'):
                    return price.amount
                return Decimal(str(price))
        except (AttributeError, TypeError):
            pass

        try:
            # Try avg_entry_price (Domain entity style)
            if hasattr(position, 'avg_entry_price') and position.avg_entry_price is not None:
                price = position.avg_entry_price
                if hasattr(price, 'amount'):
                    return price.amount
                return Decimal(str(price))
        except (AttributeError, TypeError):
            pass

        return Decimal("0")
