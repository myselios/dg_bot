---
name: trading-review
description: Reviews trading bot code for best practices, security, and performance. Use when reviewing trading logic, AI service code, or backtesting strategies.
allowed-tools: Read, Grep, Glob
---

# Trading Bot Code Review Skill

When reviewing trading bot code, check for:

## Security
- API keys not hardcoded
- No sensitive data in logs
- Proper error handling for API calls

## Trading Logic
- Fee calculation accuracy
- Slippage handling
- Order execution edge cases
- Position management safety

## AI Integration
- Prompt injection prevention
- Response validation
- Token usage optimization
- Fallback handling

## Performance
- Database query efficiency
- API rate limit handling
- Memory usage in backtesting

Always reference existing patterns in `src/trading/service.py` and `src/ai/service.py`.
