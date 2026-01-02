---
name: tdd-helper
description: Helps write tests following TDD principles. Use when writing tests, implementing features with TDD, or asking about test patterns.
---

# TDD Helper Skill

This project follows strict TDD (Test-Driven Development).

## TDD Cycle
1. **Red**: Write a failing test first
2. **Green**: Write minimal code to pass
3. **Refactor**: Improve while keeping tests green

## Test Structure
```python
def test_should_do_something(self):
    # Given - setup
    ...
    # When - action
    ...
    # Then - assertion
    ...
```

## Naming Convention
- Test files: `test_<module_name>.py`
- Test classes: `Test<ClassName>`
- Test methods: `test_should_<expected_behavior>`

## Markers
- `@pytest.mark.unit` - fast, isolated tests
- `@pytest.mark.integration` - tests with external dependencies

## Running Tests
```bash
python -m pytest tests/ -v
python -m pytest tests/test_module.py::TestClass::test_method -v
```

Always write the test BEFORE implementing the feature.
