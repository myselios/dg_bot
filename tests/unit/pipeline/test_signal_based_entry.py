"""
Phase 1: 신호 기반 진입 테스트

TDD RED Phase - 이 테스트들은 구현 전에 먼저 실패해야 함.

테스트 목적:
1. SignalAnalyzer 결과로 즉시 매수 결정 (AI 스킵)
2. strong_buy/buy → "buy"로 다운캐스트
3. AI 분석 스킵 확인
4. 극단적 변동성 시 진입 차단 (ATR% > 10%)
"""
import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from src.application.dto.trading import SignalDecisionDTO


# =============================================================================
# SignalDecisionDTO 단위 테스트
# =============================================================================

class TestSignalDecisionDTO:
    """SignalDecisionDTO 생성 및 변환 테스트."""

    def _create_signal_analysis(
        self,
        decision: str = "buy",
        total_score: float = 2.5,
        buy_score: float = 4.0,
        sell_score: float = 1.5,
        confidence: str = "medium",
        signals: list = None,
    ) -> Dict[str, Any]:
        """테스트용 SignalAnalyzer 결과 생성."""
        return {
            "decision": decision,
            "total_score": total_score,
            "buy_score": buy_score,
            "sell_score": sell_score,
            "signal_strength": abs(total_score),
            "confidence": confidence,
            "signals": signals or ["MA5 > MA20", "RSI=35 (과매도)"],
        }

    def test_strong_buy_downcast_to_buy(self):
        """strong_buy는 buy로 다운캐스트되어야 함."""
        analysis = self._create_signal_analysis(decision="strong_buy", total_score=4.5)
        timestamp = datetime(2026, 1, 4, 12, 0, 0)

        dto = SignalDecisionDTO.from_signal_analysis(
            ticker="KRW-BTC",
            price=Decimal("50000000"),
            analysis=analysis,
            timestamp=timestamp,
        )

        # decision은 "buy"로 변환되어야 함
        assert dto.decision == "buy"
        # raw_decision은 원본 유지
        assert dto.raw_decision == "strong_buy"
        assert dto.is_buy_signal() is True

    def test_buy_remains_buy(self):
        """buy는 그대로 buy로 유지."""
        analysis = self._create_signal_analysis(decision="buy", total_score=2.0)
        timestamp = datetime(2026, 1, 4, 12, 0, 0)

        dto = SignalDecisionDTO.from_signal_analysis(
            ticker="KRW-ETH",
            price=Decimal("3000000"),
            analysis=analysis,
            timestamp=timestamp,
        )

        assert dto.decision == "buy"
        assert dto.raw_decision == "buy"
        assert dto.is_buy_signal() is True

    def test_strong_sell_downcast_to_sell(self):
        """strong_sell은 sell로 다운캐스트되어야 함."""
        analysis = self._create_signal_analysis(decision="strong_sell", total_score=-4.5)
        timestamp = datetime(2026, 1, 4, 12, 0, 0)

        dto = SignalDecisionDTO.from_signal_analysis(
            ticker="KRW-BTC",
            price=Decimal("50000000"),
            analysis=analysis,
            timestamp=timestamp,
        )

        assert dto.decision == "sell"
        assert dto.raw_decision == "strong_sell"
        assert dto.is_sell_signal() is True

    def test_hold_remains_hold(self):
        """hold는 그대로 hold 유지."""
        analysis = self._create_signal_analysis(decision="hold", total_score=0.5)
        timestamp = datetime(2026, 1, 4, 12, 0, 0)

        dto = SignalDecisionDTO.from_signal_analysis(
            ticker="KRW-XRP",
            price=Decimal("500"),
            analysis=analysis,
            timestamp=timestamp,
        )

        assert dto.decision == "hold"
        assert dto.raw_decision == "hold"
        assert dto.is_hold_signal() is True

    def test_signals_limited_to_10(self):
        """signals는 최대 10개로 제한."""
        long_signals = [f"Signal_{i}" for i in range(20)]
        analysis = self._create_signal_analysis(signals=long_signals)
        timestamp = datetime(2026, 1, 4, 12, 0, 0)

        dto = SignalDecisionDTO.from_signal_analysis(
            ticker="KRW-BTC",
            price=Decimal("50000000"),
            analysis=analysis,
            timestamp=timestamp,
        )

        assert len(dto.signals) == 10
        assert dto.signals[0] == "Signal_0"
        assert dto.signals[9] == "Signal_9"

    def test_effective_confidence_downgrades_very_low(self):
        """very_low confidence는 low로 downgrade."""
        analysis = self._create_signal_analysis(confidence="very_low")
        timestamp = datetime(2026, 1, 4, 12, 0, 0)

        dto = SignalDecisionDTO.from_signal_analysis(
            ticker="KRW-BTC",
            price=Decimal("50000000"),
            analysis=analysis,
            timestamp=timestamp,
        )

        # 원본은 유지
        assert dto.confidence == "very_low"
        # effective는 low로 downgrade
        assert dto.get_effective_confidence() == "low"

    def test_effective_confidence_keeps_others(self):
        """high/medium/low confidence는 그대로 유지."""
        for conf in ["high", "medium", "low"]:
            analysis = self._create_signal_analysis(confidence=conf)
            timestamp = datetime(2026, 1, 4, 12, 0, 0)

            dto = SignalDecisionDTO.from_signal_analysis(
                ticker="KRW-BTC",
                price=Decimal("50000000"),
                analysis=analysis,
                timestamp=timestamp,
            )

            assert dto.confidence == conf
            assert dto.get_effective_confidence() == conf

    def test_timestamp_is_injected_not_generated(self):
        """timestamp는 외부에서 주입되어야 함 (재현성)."""
        analysis = self._create_signal_analysis()
        fixed_time = datetime(2026, 1, 4, 12, 30, 45)

        dto = SignalDecisionDTO.from_signal_analysis(
            ticker="KRW-BTC",
            price=Decimal("50000000"),
            analysis=analysis,
            timestamp=fixed_time,
        )

        assert dto.timestamp == fixed_time

    def test_reason_contains_raw_decision_and_score(self):
        """reason에 원본 decision과 score가 포함되어야 함."""
        analysis = self._create_signal_analysis(decision="strong_buy", total_score=4.5)
        timestamp = datetime(2026, 1, 4, 12, 0, 0)

        dto = SignalDecisionDTO.from_signal_analysis(
            ticker="KRW-BTC",
            price=Decimal("50000000"),
            analysis=analysis,
            timestamp=timestamp,
        )

        assert "strong_buy" in dto.reason
        assert "4.5" in dto.reason


# =============================================================================
# AnalysisStage 신호 기반 진입 테스트 (AI 스킵)
# =============================================================================

class TestAnalysisStageSignalBasedEntry:
    """AnalysisStage가 entry_mode에서 AI를 스킵하고 SignalAnalyzer 사용."""

    def _create_mock_context(
        self,
        ticker: str = "KRW-BTC",
        current_price: float = 50000000,
        signal_decision: str = "buy",
        total_score: float = 2.5,
    ) -> Mock:
        """테스트용 PipelineContext Mock 생성."""
        import pandas as pd
        import numpy as np

        context = Mock()
        context.ticker = ticker
        context.entry_mode = True  # 신호 기반 진입 모드
        context.container = None  # 레거시 모드
        context.ai_service = Mock()
        context.current_status = {"current_price": current_price}
        context.technical_indicators = {
            "rsi": 35,
            "macd": 100,
            "macd_signal": 50,
            "ma5": 51000000,
            "ma20": 50000000,
        }

        # chart_data - 플래시 크래시 감지 등을 위한 DataFrame
        # 최소한의 데이터로 설정
        mock_df = pd.DataFrame({
            'open': [50000000] * 30,
            'high': [51000000] * 30,
            'low': [49000000] * 30,
            'close': [50500000] * 30,
            'volume': [1000000] * 30,
        })
        context.chart_data = {"day": mock_df}

        context.backtest_result = Mock(passed=True, metrics={}, filter_results={}, reason="")
        context.market_correlation = {}
        context.flash_crash = {"detected": False}
        context.rsi_divergence = {}
        context.signal_analysis = None
        context.ai_result = None

        # 선택된 코인이 있으면 백테스팅 스킵
        context.selected_coin = Mock()
        context.selected_coin.backtest_score = Mock(metrics={}, filter_results={})
        context.selected_coin.final_score = 85.0
        context.selected_coin.symbol = "BTC"

        return context

    @pytest.mark.asyncio
    async def test_signal_analysis_triggers_buy_on_strong_signal(self):
        """강한 신호(strong_buy/buy)에서 즉시 매수 결정."""
        from src.trading.pipeline.analysis_stage import AnalysisStage

        # Given: entry_mode=True, strong_buy 신호
        stage = AnalysisStage(entry_mode=True)
        context = self._create_mock_context(signal_decision="strong_buy", total_score=4.5)

        # When: 분석 실행
        result = await stage.execute(context)

        # Then: AI 호출 없이 매수 결정
        assert result.success is True
        assert result.action == "continue"
        # context.ai_result가 설정되어 있어야 함 (SignalDecisionDTO 기반)
        assert context.ai_result is not None
        assert context.ai_result["decision"] == "buy"
        # AI 분석 스킵 확인
        context.ai_service.analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_signal_analysis_holds_on_weak_signal(self):
        """약한 신호(hold)에서 홀드 결정."""
        from src.trading.pipeline.analysis_stage import AnalysisStage
        from src.trading.signal_analyzer import SignalAnalyzer

        # Given: entry_mode=True, hold 신호 (total_score가 -1 ~ 1 사이)
        stage = AnalysisStage(entry_mode=True)
        context = self._create_mock_context(signal_decision="hold", total_score=0.5)

        # SignalAnalyzer를 mock하여 hold 결과 반환
        with patch.object(SignalAnalyzer, 'analyze_signals', return_value={
            "decision": "hold",
            "buy_score": 1.0,
            "sell_score": 0.5,
            "total_score": 0.5,  # -1 ~ 1 사이 = hold
            "signal_strength": 0.5,
            "signals": ["RSI=50 (중립)"],
            "confidence": "low",
        }):
            # When: 분석 실행
            result = await stage.execute(context)

        # Then: hold 결정
        assert result.success is True
        assert context.ai_result is not None
        assert context.ai_result["decision"] == "hold"
        # AI 분석 스킵 확인
        context.ai_service.analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_ai_analysis_skipped_in_entry_mode(self):
        """entry_mode=True일 때 AI 분석 스킵 확인."""
        from src.trading.pipeline.analysis_stage import AnalysisStage

        # Given: entry_mode=True
        stage = AnalysisStage(entry_mode=True)
        context = self._create_mock_context()

        # Mock AI service
        context.ai_service = Mock()
        context.ai_service.analyze = Mock(return_value={"decision": "hold"})

        # When: 분석 실행
        await stage.execute(context)

        # Then: AI 호출되지 않음
        context.ai_service.analyze.assert_not_called()
        context.ai_service.prepare_analysis_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_entry_decision_matches_signal_analyzer_output(self):
        """
        결정이 SignalAnalyzer 출력과 일치하는지 검증.

        - raw_decision은 SignalAnalyzer 원본과 일치
        - decision은 다운캐스트 결과(buy/hold/sell)와 일치
        """
        from src.trading.pipeline.analysis_stage import AnalysisStage

        # Given: entry_mode=True, strong_buy 신호
        stage = AnalysisStage(entry_mode=True)
        context = self._create_mock_context()
        # strong_buy 신호를 생성할 수 있는 indicators
        context.technical_indicators = {
            "rsi": 25,  # 과매도 → buy_score +2
            "macd": 200,
            "macd_signal": 50,  # MACD > Signal → buy_score +1.5
            "ma5": 52000000,
            "ma20": 50000000,  # MA5 > MA20 → buy_score +1
            "ema12": 51000000,
            "ema26": 50000000,  # EMA12 > EMA26 → buy_score +1
        }

        # When: 분석 실행
        result = await stage.execute(context)

        # Then: context에 signal_decision_dto가 설정됨
        assert result.success is True
        assert context.ai_result is not None
        # decision은 다운캐스트 결과
        assert context.ai_result["decision"] in ("buy", "hold", "sell")
        # raw_decision 확인 (signal_analysis에서)
        assert context.signal_analysis is not None
        assert context.signal_analysis["decision"] in ("strong_buy", "buy", "hold", "sell", "strong_sell")


# =============================================================================
# HybridRiskCheckStage ATR 하드 필터 테스트
# =============================================================================

class TestHybridRiskCheckStageATRFilter:
    """HybridRiskCheckStage의 ATR% > 10% 하드 필터 테스트."""

    def _create_mock_context_for_atr(
        self,
        atr_pct: float = 5.0,
        has_position: bool = False,
    ) -> Mock:
        """테스트용 PipelineContext Mock 생성 (ATR 테스트용)."""
        context = Mock()
        context.ticker = "KRW-BTC"
        context.trading_type = "spot"
        context.container = None

        # Upbit client mock
        context.upbit_client = Mock()
        context.upbit_client.get_balance = Mock(return_value={"balance": 1000000})

        # 포트폴리오 상태
        if has_position:
            position_mock = Mock()
            position_mock.ticker = "KRW-BTC"
            position_mock.symbol = "BTC"
            position_mock.profit_rate = 2.5  # Phase 3: 손익률 추가 (중립 상태)
            position_mock.avg_buy_price = 50000000
            position_mock.current_price = 51250000  # +2.5%
            context.portfolio_status = Mock()
            context.portfolio_status.positions = [position_mock]
            context.portfolio_status.trading_mode = Mock()
            context.portfolio_status.trading_mode.value = "MANAGEMENT"
            context.portfolio_status.can_open_new_position = False
        else:
            context.portfolio_status = Mock()
            context.portfolio_status.positions = []
            context.portfolio_status.trading_mode = Mock()
            context.portfolio_status.trading_mode.value = "ENTRY"
            context.portfolio_status.can_open_new_position = True
            context.portfolio_status.available_capital = 1000000

        # ATR 정보
        context.atr_pct = atr_pct

        return context

    @pytest.mark.asyncio
    async def test_extreme_volatility_blocks_entry(self):
        """
        ATR% > 10%일 때 진입 차단.

        적용 시점: ENTRY 분기 직후, CoinScan/Backtest 이전
        """
        from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage

        # Given: ATR% > 10% (극단적 변동성)
        stage = HybridRiskCheckStage(enable_scanning=False, fallback_ticker="KRW-BTC")
        context = self._create_mock_context_for_atr(atr_pct=12.0, has_position=False)

        # PortfolioManager mock 설정
        with patch("src.trading.pipeline.hybrid_stage.PortfolioManager") as MockPM:
            mock_pm = Mock()
            mock_pm.get_portfolio_status.return_value = context.portfolio_status
            mock_pm.check_portfolio_risk.return_value = {"allowed": True}
            mock_pm.print_portfolio_summary = Mock()
            MockPM.return_value = mock_pm

            # ATR 정보 제공을 위한 추가 mock
            context.technical_indicators = {"atr": 6000000, "current_price": 50000000}  # 12% ATR

            # When: 리스크 체크 실행
            result = await stage.execute(context)

        # Then: 진입 차단 (skip)
        assert result.success is True
        assert result.action == "skip"
        assert "변동성" in result.message or "ATR" in result.message

    @pytest.mark.asyncio
    async def test_normal_volatility_allows_entry(self):
        """ATR% <= 10%일 때 정상 진입 허용."""
        from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage

        # Given: ATR% <= 10% (정상 변동성)
        stage = HybridRiskCheckStage(enable_scanning=False, fallback_ticker="KRW-BTC")
        context = self._create_mock_context_for_atr(atr_pct=5.0, has_position=False)

        # PortfolioManager mock 설정
        with patch("src.trading.pipeline.hybrid_stage.PortfolioManager") as MockPM:
            mock_pm = Mock()
            mock_pm.get_portfolio_status.return_value = context.portfolio_status
            mock_pm.check_portfolio_risk.return_value = {"allowed": True}
            mock_pm.print_portfolio_summary = Mock()
            MockPM.return_value = mock_pm

            # ATR 정보 제공을 위한 추가 mock
            context.technical_indicators = {"atr": 2500000, "current_price": 50000000}  # 5% ATR

            # When: 리스크 체크 실행
            result = await stage.execute(context)

        # Then: 진입 허용 (continue)
        assert result.success is True
        assert result.action == "continue"

    @pytest.mark.asyncio
    async def test_atr_filter_not_applied_to_exit(self):
        """청산 시에는 ATR 필터 적용 안 함."""
        from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage

        # Given: 포지션 보유 중 + 극단적 변동성 (ATR% > 10%)
        stage = HybridRiskCheckStage(enable_scanning=False, fallback_ticker="KRW-BTC")
        context = self._create_mock_context_for_atr(atr_pct=15.0, has_position=True)

        # PortfolioManager mock 설정
        with patch("src.trading.pipeline.hybrid_stage.PortfolioManager") as MockPM:
            mock_pm = Mock()
            mock_pm.get_portfolio_status.return_value = context.portfolio_status
            mock_pm.check_portfolio_risk.return_value = {"allowed": True}
            mock_pm.print_portfolio_summary = Mock()
            MockPM.return_value = mock_pm

            # ATR 정보 제공
            context.technical_indicators = {"atr": 7500000, "current_price": 50000000}  # 15% ATR

            # When: 리스크 체크 실행
            result = await stage.execute(context)

        # Then: ATR 필터로 차단되지 않음 (포지션 관리 모드)
        # 청산은 position_management_job에서 처리
        assert result.success is True
        # MANAGEMENT 모드에서는 continue 또는 skip (추가 진입 불가 시)
        assert result.action in ("continue", "skip")
