"""
ValidationAdapter - AI 응답 검증 어댑터

AI 응답 형식 검증, 판단 일관성 검사, JSON 스키마 검증을 담당합니다.
"""
from typing import Any, Dict, Optional

from src.application.ports.outbound.validation_port import (
    ValidationPort,
    ValidationResult,
)
from src.domain.value_objects.ai_decision_result import AIDecisionResult, DecisionType


# Valid decision values (including aliases for backward compatibility)
VALID_DECISIONS = {"allow", "block", "hold", "buy", "sell", "wait"}

# JSON schemas for validation
SCHEMAS = {
    "decision": {
        "required": ["decision", "confidence"],
        "properties": {
            "decision": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 100},
            "reason": {"type": "string"},
        },
    },
}


class ValidationAdapter(ValidationPort):
    """
    AI 응답 검증 어댑터.

    Features:
    - AI 응답 형식 검증 (필수 필드, 데이터 타입)
    - 판단과 시장 컨텍스트 일관성 검사
    - JSON 스키마 검증
    - 커스텀 검증 규칙 지원
    """

    def __init__(
        self,
        rsi_overbought_threshold: float = 75.0,
        rsi_oversold_threshold: float = 30.0,
        min_confidence: int = 0,
    ):
        """
        Initialize adapter.

        Args:
            rsi_overbought_threshold: RSI threshold for overbought warning
            rsi_oversold_threshold: RSI threshold for oversold warning
            min_confidence: Minimum required confidence level
        """
        self.rsi_overbought_threshold = rsi_overbought_threshold
        self.rsi_oversold_threshold = rsi_oversold_threshold
        self.min_confidence = min_confidence

    async def validate_response(
        self,
        raw_response: Dict[str, Any],
    ) -> ValidationResult:
        """
        Validate raw AI response format.

        Checks:
        - Required fields present (decision, confidence)
        - Valid decision value (allow/block/hold or aliases)
        - Confidence in valid range (0-100)
        - Minimum confidence threshold

        Args:
            raw_response: Raw response from AI

        Returns:
            ValidationResult indicating if response is valid
        """
        # Check required fields
        if "decision" not in raw_response:
            return ValidationResult(
                valid=False,
                message="Missing required field: decision",
            )

        if "confidence" not in raw_response:
            return ValidationResult(
                valid=False,
                message="Missing required field: confidence",
            )

        # Validate decision value
        decision = raw_response.get("decision", "").lower()
        if decision not in VALID_DECISIONS:
            return ValidationResult(
                valid=False,
                message=f"Invalid decision value: {decision}. Expected: {VALID_DECISIONS}",
            )

        # Validate confidence range
        confidence = raw_response.get("confidence", 0)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            return ValidationResult(
                valid=False,
                message="Confidence must be a number",
            )

        if confidence < 0 or confidence > 100:
            return ValidationResult(
                valid=False,
                message=f"Confidence must be 0-100, got {confidence}",
            )

        # Check minimum confidence threshold
        if confidence < self.min_confidence:
            return ValidationResult(
                valid=False,
                message=f"Confidence {confidence} below minimum {self.min_confidence}",
            )

        return ValidationResult(
            valid=True,
            message="Response validation passed",
        )

    async def validate_decision(
        self,
        decision: AIDecisionResult,
        market_context: Dict[str, Any],
    ) -> ValidationResult:
        """
        Validate AI decision against market context.

        Checks for contradictions:
        - ALLOW with overbought RSI (> threshold) -> override to HOLD
        - ALLOW with strong negative MACD -> warning

        BLOCK decisions are always considered valid (safe default).

        Args:
            decision: AI decision to validate
            market_context: Current market conditions

        Returns:
            ValidationResult with potential override
        """
        # BLOCK/HOLD decisions are always valid (safe default)
        if decision.decision in (DecisionType.BLOCK, DecisionType.HOLD):
            return ValidationResult(
                valid=True,
                message="BLOCK/HOLD decisions are always safe",
            )

        # ALLOW decision - check for contradictions
        rsi = market_context.get("rsi")
        macd_histogram = market_context.get("macd_histogram")

        warnings = []
        details: Dict[str, Any] = {}

        # Check RSI
        if rsi is not None:
            if rsi > self.rsi_overbought_threshold:
                # Hard block - override to HOLD
                return ValidationResult(
                    valid=False,
                    message=f"ALLOW with overbought RSI ({rsi}) - override to HOLD",
                    override_decision=DecisionType.HOLD,
                    details={"rsi": rsi, "threshold": self.rsi_overbought_threshold},
                )

        # Check MACD
        if macd_histogram is not None:
            if macd_histogram < -1.0:
                # Soft warning - still valid but noted
                warnings.append(f"Negative MACD histogram ({macd_histogram})")

        # No indicators available - warning
        if rsi is None and macd_histogram is None:
            details["warning"] = "No indicators available for validation"
            details["level"] = "warning"

        # Build result
        if warnings:
            details["warnings"] = warnings
            details["level"] = "warning"

        return ValidationResult(
            valid=True,
            message="Decision validation passed" + (f" with warnings: {warnings}" if warnings else ""),
            details=details if details else None,
        )

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
        schema = SCHEMAS.get(schema_name)
        if schema is None:
            return ValidationResult(
                valid=False,
                message=f"Unknown schema: {schema_name}",
            )

        # Check required fields
        required = schema.get("required", [])
        for field in required:
            if field not in data:
                return ValidationResult(
                    valid=False,
                    message=f"Missing required field: {field}",
                )

        # Check property types
        properties = schema.get("properties", {})
        for field, constraints in properties.items():
            if field not in data:
                continue

            value = data[field]
            expected_type = constraints.get("type")

            # Type checking
            if expected_type == "string" and not isinstance(value, str):
                return ValidationResult(
                    valid=False,
                    message=f"Field {field} must be a string",
                )

            if expected_type == "number" and not isinstance(value, (int, float)):
                return ValidationResult(
                    valid=False,
                    message=f"Field {field} must be a number",
                )

            # Range checking for numbers
            if expected_type == "number":
                minimum = constraints.get("minimum")
                maximum = constraints.get("maximum")

                if minimum is not None and value < minimum:
                    return ValidationResult(
                        valid=False,
                        message=f"Field {field} must be >= {minimum}",
                    )

                if maximum is not None and value > maximum:
                    return ValidationResult(
                        valid=False,
                        message=f"Field {field} must be <= {maximum}",
                    )

        return ValidationResult(
            valid=True,
            message="Schema validation passed",
        )
