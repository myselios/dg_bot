"""
트레이딩 엔진 테스트
TDD 원칙: 트레이딩 로직의 핵심 동작을 검증합니다.
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.trading_engine import TradingEngine


@pytest.mark.asyncio
class TestTradingEngine:
    """TradingEngine 클래스 테스트"""
    
    async def test_trading_engine_initialization(
        self,
        async_session: AsyncSession,
    ):
        """
        Given: 데이터베이스 세션
        When: TradingEngine 초기화
        Then: 정상적으로 인스턴스 생성
        """
        # When
        engine = TradingEngine(async_session)
        
        # Then
        assert engine.db == async_session
        assert engine.symbol == "KRW-BTC"  # 기본값
    
    @patch('backend.app.services.trading_engine.notify_trade')
    @patch('backend.app.services.trading_engine.notify_error')
    async def test_run_success_with_hold_decision(
        self,
        mock_notify_error: AsyncMock,
        mock_notify_trade: AsyncMock,
        async_session: AsyncSession,
    ):
        """
        Given: 트레이딩 엔진
        When: run() 실행 (AI 판단: hold)
        Then: 거래 없이 성공 완료
        """
        # Given
        engine = TradingEngine(async_session)
        
        # _get_ai_decision을 hold로 Mock
        engine._get_ai_decision = AsyncMock(return_value={
            "action": "hold",
            "confidence": 50.0,
            "reason": "시장 관망",
        })
        
        # When
        result = await engine.run()
        
        # Then
        assert result["status"] == "success"
        assert result["decision"] == "hold"
        mock_notify_trade.assert_not_called()  # 거래 없음
    
    @patch('backend.app.services.trading_engine.notify_trade')
    async def test_run_success_with_buy_decision(
        self,
        mock_notify_trade: AsyncMock,
        async_session: AsyncSession,
    ):
        """
        Given: 트레이딩 엔진
        When: run() 실행 (AI 판단: buy)
        Then: 매수 실행 및 알림 전송
        """
        # Given
        engine = TradingEngine(async_session)
        
        # Mock 설정
        engine._get_ai_decision = AsyncMock(return_value={
            "action": "buy",
            "confidence": 85.0,
            "reason": "RSI 과매도",
        })
        
        engine._execute_trade = AsyncMock(return_value={
            "trade_id": "test_buy_001",
            "side": "buy",
            "price": 95000000,
            "amount": 0.001,
            "total": 95000,
            "fee": 47.5,
        })
        
        mock_notify_trade.return_value = True
        
        # When
        result = await engine.run()
        
        # Then
        assert result["status"] == "success"
        assert result["decision"] == "buy"
        engine._execute_trade.assert_called_once()
        mock_notify_trade.assert_called_once()
    
    @patch('backend.app.services.trading_engine.notify_error')
    async def test_run_handles_exception(
        self,
        mock_notify_error: AsyncMock,
        async_session: AsyncSession,
    ):
        """
        Given: 트레이딩 엔진
        When: run() 실행 중 에러 발생
        Then: 에러 핸들링 및 알림 전송
        """
        # Given
        engine = TradingEngine(async_session)
        
        # Mock에서 에러 발생
        engine._fetch_market_data = AsyncMock(
            side_effect=Exception("API 연결 실패")
        )
        
        mock_notify_error.return_value = True
        
        # When
        result = await engine.run()
        
        # Then
        assert result["status"] == "error"
        assert "API 연결 실패" in result["error"]
        mock_notify_error.assert_called_once()
    
    async def test_fetch_market_data_placeholder(
        self,
        async_session: AsyncSession,
    ):
        """
        Given: 트레이딩 엔진
        When: _fetch_market_data 호출
        Then: 빈 딕셔너리 반환 (TODO 구현 예정)
        """
        # Given
        engine = TradingEngine(async_session)
        
        # When
        result = await engine._fetch_market_data()
        
        # Then
        assert isinstance(result, dict)
        assert result == {}
    
    async def test_calculate_indicators_placeholder(
        self,
        async_session: AsyncSession,
    ):
        """
        Given: 트레이딩 엔진과 시장 데이터
        When: _calculate_indicators 호출
        Then: 빈 딕셔너리 반환 (TODO 구현 예정)
        """
        # Given
        engine = TradingEngine(async_session)
        market_data = {"price": 95000000}
        
        # When
        result = await engine._calculate_indicators(market_data)
        
        # Then
        assert isinstance(result, dict)
        assert result == {}
    
    async def test_get_ai_decision_default(
        self,
        async_session: AsyncSession,
    ):
        """
        Given: 트레이딩 엔진
        When: _get_ai_decision 호출 (실제 AI 연동 전)
        Then: 기본 hold 판단 반환
        """
        # Given
        engine = TradingEngine(async_session)
        market_data = {}
        indicators = {}
        
        # When
        result = await engine._get_ai_decision(market_data, indicators)
        
        # Then
        assert result["action"] == "hold"
        assert "confidence" in result
        assert "reason" in result
    
    async def test_save_ai_decision(
        self,
        async_session: AsyncSession,
    ):
        """
        Given: AI 판단 결과
        When: _save_ai_decision 호출
        Then: 데이터베이스에 저장
        """
        # Given
        engine = TradingEngine(async_session)
        decision = {
            "action": "buy",
            "confidence": 85.5,
            "reason": "RSI 과매도 구간 진입",
        }
        
        # When
        await engine._save_ai_decision(decision)
        
        # Then
        # 저장 성공 확인 (예외 발생하지 않음)
        await async_session.commit()
    
    async def test_execute_trade_placeholder(
        self,
        async_session: AsyncSession,
    ):
        """
        Given: 거래 결정
        When: _execute_trade 호출 (실제 거래소 연동 전)
        Then: None 반환 (TODO 구현 예정)
        """
        # Given
        engine = TradingEngine(async_session)
        decision = {"action": "buy"}
        
        # When
        result = await engine._execute_trade(decision)
        
        # Then
        assert result is None



