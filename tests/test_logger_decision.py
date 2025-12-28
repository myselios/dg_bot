"""
로거 판단 출력 테스트
"""
import pytest
from src.utils.logger import Logger


class TestLoggerDecision:
    """Logger 판단 출력 테스트"""
    
    @pytest.mark.unit
    def test_print_decision_korean_translation(self, capsys):
        """판단 결과 한글 변환 테스트"""
        Logger.print_decision("buy", "high", "기술적 지표가 상승 추세를 보입니다")
        
        output = capsys.readouterr().out
        assert "매수" in output
        assert "높음" in output
        assert "기술적 지표가 상승 추세를 보입니다" in output
    
    @pytest.mark.unit
    def test_print_decision_sell_translation(self, capsys):
        """매도 판단 한글 변환 테스트"""
        Logger.print_decision("sell", "medium", "과매수 구간에 진입했습니다")
        
        output = capsys.readouterr().out
        assert "매도" in output
        assert "보통" in output
    
    @pytest.mark.unit
    def test_print_decision_hold_translation(self, capsys):
        """보유 판단 한글 변환 테스트"""
        Logger.print_decision("hold", "low", "현재 시장 상황을 관망하는 것이 좋습니다")
        
        output = capsys.readouterr().out
        assert "보유" in output
        assert "낮음" in output
    
    @pytest.mark.unit
    def test_print_decision_strong_buy(self, capsys):
        """강력 매수 판단 테스트"""
        Logger.print_decision("strong_buy", "high", "매우 강한 매수 신호입니다")
        
        output = capsys.readouterr().out
        assert "강력 매수" in output
    
    @pytest.mark.unit
    def test_print_decision_unknown_decision(self, capsys):
        """알 수 없는 판단 처리 테스트"""
        Logger.print_decision("unknown", "unknown", "알 수 없는 판단")
        
        output = capsys.readouterr().out
        # 알 수 없는 값은 그대로 대문자로 표시
        assert "UNKNOWN" in output





