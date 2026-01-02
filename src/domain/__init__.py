"""
Domain Layer - Pure Business Logic

This module contains the core domain logic with zero external dependencies.
All business rules, entities, value objects, and domain services reside here.

Structure:
- entities/: Core business entities (Trade, Order, Position)
- value_objects/: Immutable value objects (Money, Percentage)
- services/: Domain services (FeeCalculator, RiskCalculator)
- exceptions.py: Domain-specific exceptions
"""
