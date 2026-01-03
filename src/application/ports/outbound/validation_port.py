"""
ValidationPort - Interface for validation operations.

This port defines the contract for validating AI responses and decisions.
Adapters implementing this interface handle JSON schema validation,
rule-based checks, and decision override logic.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.domain.value_objects.ai_decision_result import AIDecisionResult, DecisionType


@dataclass
class ValidationResult:
    """
    Validation result.

    Attributes:
        valid: Whether validation passed
        message: Validation message/reason
        override_decision: If invalid, suggested override decision
        details: Additional validation details
    """

    valid: bool
    message: str
    override_decision: Optional[DecisionType] = None
    details: Optional[Dict[str, Any]] = None


class ValidationPort(ABC):
    """
    Port interface for validation operations.

    This interface defines operations for validating AI responses,
    checking decision consistency, and enforcing business rules.
    """

    @abstractmethod
    async def validate_response(
        self,
        raw_response: Dict[str, Any],
    ) -> ValidationResult:
        """
        Validate raw AI response format.

        Args:
            raw_response: Raw response from AI

        Returns:
            ValidationResult indicating if response is valid

        Note:
            Checks required fields, data types, value ranges
        """
        pass

    @abstractmethod
    async def validate_decision(
        self,
        decision: AIDecisionResult,
        market_context: Dict[str, Any],
    ) -> ValidationResult:
        """
        Validate AI decision against market context.

        Args:
            decision: AI decision to validate
            market_context: Current market conditions

        Returns:
            ValidationResult with potential override

        Note:
            Checks for contradictions (e.g., ALLOW with RSI > 70)
        """
        pass

    @abstractmethod
    async def validate_json_schema(
        self,
        data: Dict[str, Any],
        schema_name: str,
    ) -> ValidationResult:
        """
        Validate data against JSON schema.

        Args:
            data: Data to validate
            schema_name: Name of schema to use

        Returns:
            ValidationResult indicating schema compliance
        """
        pass
