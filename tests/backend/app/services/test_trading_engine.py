"""
트레이딩 엔진 테스트
TDD 원칙: 트레이딩 엔진의 전체 프로세스를 검증합니다.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from decimal import Decimal

from backend.app.services.trading_engine import TradingEngine, run_trading_cycle


@pytest.mark.asyncio
class TestTradingEngine:
    """TradingEngine 클래스 테스트"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock 데이터베이스 세션"""
        mock_session = AsyncMock()
        return mock_session
    
    @pytest.fixture
    def trading_engine(self, mock_db_session):
        """TradingEngine 인스턴스"""
        return TradingEngine(db_session=mock_db_session)
    
    @pytest.mark.unit
    async def test_engine_initialization(self, mock_db_session):
        """엔진 초기화 테스트"""
        # When
        engine = TradingEngine(db_session=mock_db_session)
        
        # Then
        assert engine is not None
        assert engine.db == mock_db_session
        assert hasattr(engine, 'symbol')
    
    @pytest.mark.unit
    async def test_run_success_with_hold_decision(self, trading_engine):
        """HOLD 결정으로 정상 실행"""
        # When
        result = await trading_engine.run()
        
        # Then
        assert result["status"] == "success"
        assert result["decision"] == "hold"
        assert "timestamp" in result
        trading_engine.db.commit.assert_called()
    
    @pytest.mark.unit
    async def test_run_with_buy_decision(self, trading_engine):
        """매수 결정 처리"""
        # Given
        with patch.object(trading_engine, '_get_ai_decision') as mock_ai:
            mock_ai.return_value = {
                "action": "buy",
                "confidence": 85.0,
                "reason": "강한 매수 시그널"
            }
            
            with patch.object(trading_engine, '_execute_trade') as mock_trade:
                mock_trade.return_value = {
                    "trade_id": "test-123",
                    "side": "bid",
                    "price": 3500000.0,
                    "amount": 0.1,
                    "total": 350000.0,
                    "fee": 175.0
                }
                
                with patch('backend.app.services.trading_engine.notify_trade') as mock_notify:
                    # When
                    result = await trading_engine.run()
        
        # Then
        assert result["status"] == "success"
        assert result["decision"] == "buy"
        mock_trade.assert_called_once()
        mock_notify.assert_called_once()
        assert trading_engine.db.add.call_count >= 2  # AI 결정 + 거래 저장
        assert trading_engine.db.commit.call_count >= 2
    
    @pytest.mark.unit
    async def test_run_with_sell_decision(self, trading_engine):
        """매도 결정 처리"""
        # Given
        with patch.object(trading_engine, '_get_ai_decision') as mock_ai:
            mock_ai.return_value = {
                "action": "sell",
                "confidence": 90.0,
                "reason": "익절 시점"
            }
            
            with patch.object(trading_engine, '_execute_trade') as mock_trade:
                mock_trade.return_value = {
                    "trade_id": "test-456",
                    "side": "ask",
                    "price": 3600000.0,
                    "amount": 0.1,
                    "total": 360000.0,
                    "fee": 180.0
                }
                
                with patch('backend.app.services.trading_engine.notify_trade') as mock_notify:
                    # When
                    result = await trading_engine.run()
        
        # Then
        assert result["status"] == "success"
        assert result["decision"] == "sell"
        mock_trade.assert_called_once()
        mock_notify.assert_called_once()
    
    @pytest.mark.unit
    async def test_run_with_trade_execution_failure(self, trading_engine):
        """거래 실행 실패 처리"""
        # Given
        with patch.object(trading_engine, '_get_ai_decision') as mock_ai:
            mock_ai.return_value = {
                "action": "buy",
                "confidence": 80.0,
                "reason": "매수 시도"
            }
            
            with patch.object(trading_engine, '_execute_trade') as mock_trade:
                mock_trade.return_value = None  # 거래 실패
                
                # When
                result = await trading_engine.run()
        
        # Then
        assert result["status"] == "success"
        assert result["decision"] == "buy"
        # 거래 실패 시 거래 결과는 저장되지 않음
        # AI 결정만 저장됨
        assert trading_engine.db.add.call_count >= 1
    
    @pytest.mark.unit
    async def test_run_with_exception(self, trading_engine):
        """예외 발생 시 에러 처리"""
        # Given
        with patch.object(trading_engine, '_fetch_market_data') as mock_fetch:
            mock_fetch.side_effect = Exception("API 오류")
            
            with patch('backend.app.services.trading_engine.notify_error') as mock_notify_error:
                # When
                result = await trading_engine.run()
        
        # Then
        assert result["status"] == "error"
        assert "API 오류" in result["error"]
        assert "timestamp" in result
        mock_notify_error.assert_called_once()
    
    @pytest.mark.unit
    async def test_fetch_market_data(self, trading_engine):
        """시장 데이터 수집"""
        # When
        market_data = await trading_engine._fetch_market_data()
        
        # Then
        assert isinstance(market_data, dict)
    
    @pytest.mark.unit
    async def test_calculate_indicators(self, trading_engine):
        """기술적 지표 계산"""
        # Given
        market_data = {"price": 3500000, "volume": 1000}
        
        # When
        indicators = await trading_engine._calculate_indicators(market_data)
        
        # Then
        assert isinstance(indicators, dict)
    
    @pytest.mark.unit
    async def test_get_ai_decision(self, trading_engine):
        """AI 판단 요청"""
        # Given
        market_data = {}
        indicators = {}
        
        # When
        decision = await trading_engine._get_ai_decision(market_data, indicators)
        
        # Then
        assert "action" in decision
        assert decision["action"] in ["buy", "sell", "hold"]
        assert "confidence" in decision
        assert "reason" in decision
    
    @pytest.mark.unit
    async def test_save_ai_decision(self, trading_engine):
        """AI 판단 저장"""
        # Given
        decision = {
            "action": "buy",
            "confidence": 85.0,
            "reason": "테스트 매수"
        }
        
        # When
        await trading_engine._save_ai_decision(decision)
        
        # Then
        trading_engine.db.add.assert_called_once()
        trading_engine.db.commit.assert_called_once()
        
        # 저장된 객체 확인
        saved_decision = trading_engine.db.add.call_args[0][0]
        assert saved_decision.decision == "buy"
        assert saved_decision.confidence == Decimal("85.0")
        assert saved_decision.reason == "테스트 매수"
    
    @pytest.mark.unit
    async def test_execute_trade_buy(self, trading_engine):
        """매수 거래 실행"""
        # Given
        decision = {
            "action": "buy",
            "confidence": 80.0
        }
        
        # When
        result = await trading_engine._execute_trade(decision)
        
        # Then
        # 현재는 None 반환 (TODO로 표시된 부분)
        assert result is None
    
    @pytest.mark.unit
    async def test_save_trade(self, trading_engine):
        """거래 결과 저장"""
        # Given
        trade_result = {
            "trade_id": "test-uuid-789",
            "side": "bid",
            "price": 3500000.0,
            "amount": 0.1,
            "total": 350000.0,
            "fee": 175.0
        }
        
        # When
        await trading_engine._save_trade(trade_result)
        
        # Then
        trading_engine.db.add.assert_called_once()
        trading_engine.db.commit.assert_called_once()
        
        # 저장된 객체 확인
        saved_trade = trading_engine.db.add.call_args[0][0]
        assert saved_trade.trade_id == "test-uuid-789"
        assert saved_trade.side == "bid"
        assert saved_trade.price == Decimal("3500000.0")
        assert saved_trade.amount == Decimal("0.1")
        assert saved_trade.total == Decimal("350000.0")
        assert saved_trade.fee == Decimal("175.0")
        assert saved_trade.status == "completed"


@pytest.mark.asyncio
class TestRunTradingCycle:
    """run_trading_cycle 함수 테스트"""
    
    @pytest.mark.unit
    async def test_run_trading_cycle_success(self):
        """트레이딩 사이클 실행 성공"""
        # Given
        mock_session = AsyncMock()
        
        with patch('backend.app.services.trading_engine.TradingEngine') as MockEngine:
            mock_engine_instance = MockEngine.return_value
            mock_engine_instance.run = AsyncMock(return_value={
                "status": "success",
                "decision": "hold",
                "timestamp": "2024-01-01T12:00:00"
            })
            
            # When
            result = await run_trading_cycle(mock_session)
        
        # Then
        assert result["status"] == "success"
        assert result["decision"] == "hold"
        MockEngine.assert_called_once_with(mock_session)
        mock_engine_instance.run.assert_called_once()
    
    @pytest.mark.unit
    async def test_run_trading_cycle_with_error(self):
        """트레이딩 사이클 실행 중 에러"""
        # Given
        mock_session = AsyncMock()
        
        with patch('backend.app.services.trading_engine.TradingEngine') as MockEngine:
            mock_engine_instance = MockEngine.return_value
            mock_engine_instance.run = AsyncMock(return_value={
                "status": "error",
                "error": "테스트 오류",
                "timestamp": "2024-01-01T12:00:00"
            })
            
            # When
            result = await run_trading_cycle(mock_session)
        
        # Then
        assert result["status"] == "error"
        assert "error" in result


@pytest.mark.asyncio
class TestTradingEngineIntegration:
    """트레이딩 엔진 통합 테스트"""
    
    @pytest.mark.integration
    async def test_full_trading_cycle_with_buy(self):
        """전체 매수 사이클 통합 테스트"""
        # Given
        mock_session = AsyncMock()
        engine = TradingEngine(db_session=mock_session)
        
        # Mock 설정
        with patch.object(engine, '_fetch_market_data') as mock_fetch, \
             patch.object(engine, '_calculate_indicators') as mock_calc, \
             patch.object(engine, '_get_ai_decision') as mock_ai, \
             patch.object(engine, '_execute_trade') as mock_trade, \
             patch('backend.app.services.trading_engine.notify_trade') as mock_notify:
            
            mock_fetch.return_value = {"price": 3500000}
            mock_calc.return_value = {"rsi": 35, "macd": 100}
            mock_ai.return_value = {
                "action": "buy",
                "confidence": 88.0,
                "reason": "RSI oversold + MACD 골든크로스"
            }
            mock_trade.return_value = {
                "trade_id": "integration-test-123",
                "side": "bid",
                "price": 3500000.0,
                "amount": 0.1,
                "total": 350000.0,
                "fee": 175.0
            }
            
            # When
            result = await engine.run()
        
        # Then
        assert result["status"] == "success"
        assert result["decision"] == "buy"
        mock_fetch.assert_called_once()
        mock_calc.assert_called_once()
        mock_ai.assert_called_once()
        mock_trade.assert_called_once()
        mock_notify.assert_called_once()
        
        # 알림 호출 인자 확인
        notify_args = mock_notify.call_args[1]
        assert notify_args["side"] == "buy"
        assert notify_args["price"] == 3500000.0
        assert notify_args["amount"] == 0.1
    
    @pytest.mark.integration
    async def test_full_trading_cycle_with_hold(self):
        """전체 보유 사이클 통합 테스트"""
        # Given
        mock_session = AsyncMock()
        engine = TradingEngine(db_session=mock_session)
        
        with patch.object(engine, '_fetch_market_data') as mock_fetch, \
             patch.object(engine, '_calculate_indicators') as mock_calc, \
             patch.object(engine, '_get_ai_decision') as mock_ai:
            
            mock_fetch.return_value = {"price": 3500000}
            mock_calc.return_value = {"rsi": 50, "macd": 0}
            mock_ai.return_value = {
                "action": "hold",
                "confidence": 60.0,
                "reason": "관망 필요"
            }
            
            # When
            result = await engine.run()
        
        # Then
        assert result["status"] == "success"
        assert result["decision"] == "hold"
        # hold 결정 시 거래 실행 없음
        assert mock_session.add.call_count == 1  # AI 결정만 저장

