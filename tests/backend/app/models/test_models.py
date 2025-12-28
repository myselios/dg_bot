"""
백엔드 모델 테스트
TDD 원칙: 모델 정의와 기본 동작을 검증합니다.
"""
import pytest
from datetime import datetime
from decimal import Decimal
from backend.app.models.trade import Trade
from backend.app.models.bot_config import BotConfig
from backend.app.models.ai_decision import AIDecision
from backend.app.models.order import Order
from backend.app.models.portfolio import PortfolioSnapshot
from backend.app.models.system_log import SystemLog


class TestTradeModel:
    """Trade 모델 테스트"""
    
    @pytest.mark.unit
    def test_trade_creation(self):
        """거래 내역 생성 테스트"""
        # Given & When
        trade = Trade(
            trade_id="test-trade-001",
            symbol="KRW-ETH",
            side="buy",
            price=Decimal("3000000"),
            amount=Decimal("0.5"),
            total=Decimal("1500000"),
            fee=Decimal("750"),
            status="completed"
        )
        
        # Then
        assert trade.trade_id == "test-trade-001"
        assert trade.symbol == "KRW-ETH"
        assert trade.side == "buy"
        assert trade.price == Decimal("3000000")
        assert trade.amount == Decimal("0.5")
        assert trade.total == Decimal("1500000")
        assert trade.fee == Decimal("750")
        assert trade.status == "completed"
    
    @pytest.mark.unit
    def test_trade_repr(self):
        """거래 내역 문자열 표현 테스트"""
        # Given
        trade = Trade(
            trade_id="test-trade-001",
            symbol="KRW-ETH",
            side="sell",
            price=Decimal("3100000"),
            amount=Decimal("0.3"),
            total=Decimal("930000"),
            fee=Decimal("465"),
            status="completed"
        )
        
        # When
        repr_str = repr(trade)
        
        # Then
        assert "test-trade-001" in repr_str
        assert "sell" in repr_str
        assert "0.3" in repr_str
        assert "KRW-ETH" in repr_str


class TestBotConfigModel:
    """BotConfig 모델 테스트"""
    
    @pytest.mark.unit
    def test_bot_config_creation(self):
        """봇 설정 생성 테스트"""
        # Given & When
        config = BotConfig(
            key="trading_enabled",
            value={"enabled": True},
            description="거래 활성화 여부"
        )
        
        # Then
        assert config.key == "trading_enabled"
        assert config.value == {"enabled": True}
        assert config.description == "거래 활성화 여부"
    
    @pytest.mark.unit
    def test_bot_config_repr(self):
        """봇 설정 문자열 표현 테스트"""
        # Given
        config = BotConfig(
            key="interval_minutes",
            value={"value": 5},
            description="거래 주기 (분)"
        )
        
        # When
        repr_str = repr(config)
        
        # Then
        assert "interval_minutes" in repr_str
        assert "value" in repr_str


class TestAIDecisionModel:
    """AIDecision 모델 테스트"""
    
    @pytest.mark.unit
    def test_ai_decision_creation(self):
        """AI 결정 생성 테스트"""
        # Given & When
        decision = AIDecision(
            symbol="KRW-ETH",
            decision="buy",
            reason="상승 추세 감지",
            confidence=0.85
        )
        
        # Then
        assert decision.symbol == "KRW-ETH"
        assert decision.decision == "buy"
        assert decision.reason == "상승 추세 감지"
        assert decision.confidence == 0.85
    
    @pytest.mark.unit
    def test_ai_decision_repr(self):
        """AI 결정 문자열 표현 테스트"""
        # Given
        decision = AIDecision(
            symbol="KRW-BTC",
            decision="sell",
            reason="하락 시그널",
            confidence=0.75
        )
        
        # When
        repr_str = repr(decision)
        
        # Then
        assert "KRW-BTC" in repr_str
        assert "sell" in repr_str


class TestOrderModel:
    """Order 모델 테스트"""
    
    @pytest.mark.unit
    def test_order_creation(self):
        """주문 생성 테스트"""
        # Given & When
        order = Order(
            order_id="order-001",
            symbol="KRW-ETH",
            side="buy",
            order_type="market",
            price=Decimal("3000000"),
            amount=Decimal("0.5"),
            status="pending"
        )
        
        # Then
        assert order.order_id == "order-001"
        assert order.symbol == "KRW-ETH"
        assert order.side == "buy"
        assert order.order_type == "market"
        assert order.price == Decimal("3000000")
        assert order.amount == Decimal("0.5")
        assert order.status == "pending"
    
    @pytest.mark.unit
    def test_order_repr(self):
        """주문 문자열 표현 테스트"""
        # Given
        order = Order(
            order_id="order-002",
            symbol="KRW-BTC",
            side="sell",
            order_type="limit",
            price=Decimal("50000000"),
            amount=Decimal("0.1"),
            status="completed"
        )
        
        # When
        repr_str = repr(order)
        
        # Then
        assert "order-002" in repr_str
        assert "sell" in repr_str


class TestPortfolioSnapshotModel:
    """PortfolioSnapshot 모델 테스트"""
    
    @pytest.mark.unit
    def test_portfolio_snapshot_creation(self):
        """포트폴리오 스냅샷 생성 테스트"""
        # Given & When
        snapshot = PortfolioSnapshot(
            total_value_krw=Decimal("4800000"),
            total_value_usd=Decimal("3600"),
            positions={
                "KRW-ETH": {
                    "amount": 1.5,
                    "value": 4800000,
                    "profit_rate": 6.67
                }
            }
        )
        
        # Then
        assert snapshot.total_value_krw == Decimal("4800000")
        assert snapshot.total_value_usd == Decimal("3600")
        assert "KRW-ETH" in snapshot.positions
    
    @pytest.mark.unit
    def test_portfolio_snapshot_repr(self):
        """포트폴리오 스냅샷 문자열 표현 테스트"""
        # Given
        snapshot = PortfolioSnapshot(
            total_value_krw=Decimal("26000000"),
            total_value_usd=Decimal("19500"),
            positions={
                "KRW-BTC": {
                    "amount": 0.5,
                    "value": 26000000,
                    "profit_rate": 4.0
                }
            }
        )
        
        # When
        repr_str = repr(snapshot)
        
        # Then
        assert "26000000" in repr_str or "26,000,000" in repr_str


class TestSystemLogModel:
    """SystemLog 모델 테스트"""
    
    @pytest.mark.unit
    def test_system_log_creation(self):
        """시스템 로그 생성 테스트"""
        # Given & When
        log = SystemLog(
            level="INFO",
            message="거래 시작",
            context={"module": "trading_service", "action": "start"}
        )
        
        # Then
        assert log.level == "INFO"
        assert log.message == "거래 시작"
        assert log.context["module"] == "trading_service"
    
    @pytest.mark.unit
    def test_system_log_repr(self):
        """시스템 로그 문자열 표현 테스트"""
        # Given
        log = SystemLog(
            level="ERROR",
            message="API 오류 발생",
            context={"module": "data_collector", "error": "timeout"}
        )
        
        # When
        repr_str = repr(log)
        
        # Then
        assert "ERROR" in repr_str
        assert "API" in repr_str

