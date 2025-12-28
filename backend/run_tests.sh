#!/bin/bash
# Backend 테스트 실행 스크립트

set -e

echo "🧪 Bitcoin Trading Bot - Backend Tests"
echo "======================================"

# 현재 디렉토리 확인
if [ ! -f "pytest.ini" ]; then
    echo "❌ Error: pytest.ini not found. Please run from backend/ directory."
    exit 1
fi

# 가상 환경 활성화 (선택사항)
if [ -d "../venv/bin" ]; then
    echo "✅ Activating virtual environment..."
    source ../venv/bin/activate
fi

# 의존성 확인
echo ""
echo "📦 Checking dependencies..."
pip install -q -r ../requirements-api.txt

# 테스트 실행 옵션
TEST_TYPE=${1:-all}

echo ""
echo "🚀 Running tests: $TEST_TYPE"
echo "======================================"

case $TEST_TYPE in
    "all")
        echo "Running all tests..."
        pytest -v
        ;;
    "unit")
        echo "Running unit tests only..."
        pytest -v -m unit
        ;;
    "integration")
        echo "Running integration tests only..."
        pytest -v -m integration
        ;;
    "api")
        echo "Running API tests only..."
        pytest -v -m api
        ;;
    "coverage")
        echo "Running tests with coverage report..."
        pytest --cov=backend/app --cov-report=html --cov-report=term-missing
        echo ""
        echo "📊 Coverage report generated: htmlcov/index.html"
        ;;
    "fast")
        echo "Running fast tests only (excluding slow)..."
        pytest -v -m "not slow"
        ;;
    "watch")
        echo "Running tests in watch mode..."
        pytest-watch -- -v
        ;;
    *)
        echo "❌ Unknown test type: $TEST_TYPE"
        echo ""
        echo "Usage: ./run_tests.sh [TYPE]"
        echo ""
        echo "Available types:"
        echo "  all         - Run all tests (default)"
        echo "  unit        - Run unit tests only"
        echo "  integration - Run integration tests only"
        echo "  api         - Run API tests only"
        echo "  coverage    - Run with coverage report"
        echo "  fast        - Run fast tests only"
        echo "  watch       - Run in watch mode"
        exit 1
        ;;
esac

echo ""
echo "✅ Tests completed!"

