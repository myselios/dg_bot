"""
기술적 지표 기반 신호 분석
베스트 프랙티스에 따른 다중 지표 조합 분석
"""
from typing import Dict, Optional
import numpy as np


class SignalAnalyzer:
    """신호 분석 클래스 - 여러 지표를 조합하여 매매 신호 생성"""
    
    @staticmethod
    def analyze_signals(indicators: Dict[str, float], current_price: float) -> Dict[str, any]:
        """
        여러 지표를 조합하여 매매 신호 분석
        
        Args:
            indicators: 기술적 지표 딕셔너리
            current_price: 현재가
            
        Returns:
            신호 분석 결과 딕셔너리
        """
        buy_score = 0
        sell_score = 0
        signals = []
        
        # 1. 추세 지표 분석 (Trend Indicators)
        trend_signals = SignalAnalyzer._analyze_trend(indicators, current_price)
        buy_score += trend_signals['buy']
        sell_score += trend_signals['sell']
        signals.extend(trend_signals['signals'])
        
        # 2. 모멘텀 지표 분석 (Momentum Indicators)
        momentum_signals = SignalAnalyzer._analyze_momentum(indicators)
        buy_score += momentum_signals['buy']
        sell_score += momentum_signals['sell']
        signals.extend(momentum_signals['signals'])
        
        # 3. 변동성 지표 분석 (Volatility Indicators)
        volatility_signals = SignalAnalyzer._analyze_volatility(indicators, current_price)
        buy_score += volatility_signals['buy']
        sell_score += volatility_signals['sell']
        signals.extend(volatility_signals['signals'])
        
        # 4. 거래량 지표 분석 (Volume Indicators)
        volume_signals = SignalAnalyzer._analyze_volume(indicators)
        buy_score += volume_signals['buy']
        sell_score += volume_signals['sell']
        signals.extend(volume_signals['signals'])
        
        # 최종 신호 결정
        total_score = buy_score - sell_score
        signal_strength = abs(total_score)
        
        if total_score > 3:
            decision = "strong_buy"
        elif total_score > 1:
            decision = "buy"
        elif total_score < -3:
            decision = "strong_sell"
        elif total_score < -1:
            decision = "sell"
        else:
            decision = "hold"
        
        return {
            "decision": decision,
            "buy_score": buy_score,
            "sell_score": sell_score,
            "total_score": total_score,
            "signal_strength": signal_strength,
            "signals": signals,
            "confidence": SignalAnalyzer._calculate_confidence(signal_strength, len(signals))
        }
    
    @staticmethod
    def _analyze_trend(indicators: Dict[str, float], current_price: float) -> Dict:
        """추세 지표 분석"""
        buy_score = 0
        sell_score = 0
        signals = []
        
        # 이동평균선 분석 (골든크로스/데드크로스)
        ma5 = indicators.get('ma5')
        ma20 = indicators.get('ma20')
        ma60 = indicators.get('ma60')
        
        if ma5 and ma20:
            if ma5 > ma20:
                buy_score += 1
                signals.append("MA5 > MA20 (단기 상승 추세)")
            else:
                sell_score += 1
                signals.append("MA5 < MA20 (단기 하락 추세)")
        
        if ma20 and ma60:
            if ma20 > ma60:
                buy_score += 1
                signals.append("MA20 > MA60 (중기 상승 추세)")
            else:
                sell_score += 1
                signals.append("MA20 < MA60 (중기 하락 추세)")
        
        # 현재가와 이동평균선 비교
        if ma20 and current_price:
            if current_price > ma20:
                buy_score += 0.5
                signals.append("현재가 > MA20")
            else:
                sell_score += 0.5
                signals.append("현재가 < MA20")
        
        # EMA 분석
        ema12 = indicators.get('ema12')
        ema26 = indicators.get('ema26')
        
        if ema12 and ema26:
            if ema12 > ema26:
                buy_score += 1
                signals.append("EMA12 > EMA26 (EMA 골든크로스)")
            else:
                sell_score += 1
                signals.append("EMA12 < EMA26 (EMA 데드크로스)")
        
        # MACD 분석
        macd = indicators.get('macd')
        macd_signal = indicators.get('macd_signal')
        macd_histogram = indicators.get('macd_histogram')
        
        if macd and macd_signal:
            if macd > macd_signal:
                buy_score += 1.5
                signals.append("MACD > Signal (상승 모멘텀)")
            else:
                sell_score += 1.5
                signals.append("MACD < Signal (하락 모멘텀)")
        
        if macd_histogram:
            if macd_histogram > 0:
                buy_score += 0.5
            else:
                sell_score += 0.5
        
        # ADX (추세 강도)
        adx = indicators.get('adx')
        if adx:
            if adx > 25:
                signals.append(f"ADX={adx:.1f} (강한 추세)")
                # 강한 추세일 때는 기존 신호 가중치 증가
                if buy_score > sell_score:
                    buy_score += 0.5
                elif sell_score > buy_score:
                    sell_score += 0.5
            elif adx < 20:
                signals.append(f"ADX={adx:.1f} (약한 추세/횡보)")
        
        return {"buy": buy_score, "sell": sell_score, "signals": signals}
    
    @staticmethod
    def _analyze_momentum(indicators: Dict[str, float]) -> Dict:
        """모멘텀 지표 분석"""
        buy_score = 0
        sell_score = 0
        signals = []
        
        # RSI 분석
        rsi = indicators.get('rsi')
        if rsi:
            if rsi < 30:
                buy_score += 2
                signals.append(f"RSI={rsi:.1f} (과매도 구간)")
            elif rsi < 40:
                buy_score += 1
                signals.append(f"RSI={rsi:.1f} (약한 과매도)")
            elif rsi > 70:
                sell_score += 2
                signals.append(f"RSI={rsi:.1f} (과매수 구간)")
            elif rsi > 60:
                sell_score += 1
                signals.append(f"RSI={rsi:.1f} (약한 과매수)")
            else:
                signals.append(f"RSI={rsi:.1f} (중립)")
        
        # Stochastic 분석
        stoch_k = indicators.get('stoch_k')
        stoch_d = indicators.get('stoch_d')
        
        if stoch_k and stoch_d:
            if stoch_k < 20 and stoch_d < 20:
                buy_score += 1.5
                signals.append(f"Stochastic K={stoch_k:.1f}, D={stoch_d:.1f} (과매도)")
            elif stoch_k > 80 and stoch_d > 80:
                sell_score += 1.5
                signals.append(f"Stochastic K={stoch_k:.1f}, D={stoch_d:.1f} (과매수)")
            elif stoch_k > stoch_d:
                buy_score += 0.5
                signals.append("Stochastic K > D (상승 모멘텀)")
            else:
                sell_score += 0.5
                signals.append("Stochastic K < D (하락 모멘텀)")
        
        # MFI 분석
        mfi = indicators.get('mfi')
        if mfi:
            if mfi < 20:
                buy_score += 1
                signals.append(f"MFI={mfi:.1f} (과매도)")
            elif mfi > 80:
                sell_score += 1
                signals.append(f"MFI={mfi:.1f} (과매수)")
        
        # Williams %R 분석
        williams_r = indicators.get('williams_r')
        if williams_r:
            if williams_r < -80:
                buy_score += 1
                signals.append(f"Williams %R={williams_r:.1f} (과매도)")
            elif williams_r > -20:
                sell_score += 1
                signals.append(f"Williams %R={williams_r:.1f} (과매수)")
        
        return {"buy": buy_score, "sell": sell_score, "signals": signals}
    
    @staticmethod
    def _analyze_volatility(indicators: Dict[str, float], current_price: float) -> Dict:
        """변동성 지표 분석"""
        buy_score = 0
        sell_score = 0
        signals = []
        
        # 볼린저 밴드 분석
        bb_upper = indicators.get('bb_upper')
        bb_middle = indicators.get('bb_middle')
        bb_lower = indicators.get('bb_lower')
        
        if bb_upper and bb_lower and current_price:
            bb_width = (bb_upper - bb_lower) / bb_middle if bb_middle else 0
            
            if current_price <= bb_lower:
                buy_score += 2
                signals.append("현재가 <= 볼린저 하단 (과매도)")
            elif current_price >= bb_upper:
                sell_score += 2
                signals.append("현재가 >= 볼린저 상단 (과매수)")
            elif current_price < bb_middle:
                buy_score += 0.5
                signals.append("현재가 < 볼린저 중간선")
            else:
                sell_score += 0.5
                signals.append("현재가 > 볼린저 중간선")
            
            if bb_width > 0.1:
                signals.append(f"볼린저 밴드폭={bb_width*100:.1f}% (높은 변동성)")
        
        # CCI 분석
        cci = indicators.get('cci')
        if cci:
            if cci < -100:
                buy_score += 1
                signals.append(f"CCI={cci:.1f} (과매도)")
            elif cci > 100:
                sell_score += 1
                signals.append(f"CCI={cci:.1f} (과매수)")
        
        # ATR 분석 (변동성 크기)
        atr = indicators.get('atr')
        if atr and current_price:
            atr_pct = (atr / current_price) * 100
            if atr_pct > 5:
                signals.append(f"ATR={atr_pct:.1f}% (높은 변동성)")
        
        return {"buy": buy_score, "sell": sell_score, "signals": signals}
    
    @staticmethod
    def _analyze_volume(indicators: Dict[str, float]) -> Dict:
        """거래량 지표 분석"""
        buy_score = 0
        sell_score = 0
        signals = []
        
        # OBV 분석
        obv = indicators.get('obv')
        obv_change_pct = indicators.get('obv_change_pct')
        
        if obv_change_pct:
            if obv_change_pct > 5:
                buy_score += 1
                signals.append(f"OBV 변화율={obv_change_pct:.1f}% (거래량 급증)")
            elif obv_change_pct < -5:
                sell_score += 1
                signals.append(f"OBV 변화율={obv_change_pct:.1f}% (거래량 급감)")
        
        return {"buy": buy_score, "sell": sell_score, "signals": signals}
    
    @staticmethod
    def _calculate_confidence(signal_strength: float, signal_count: int) -> str:
        """신뢰도 계산"""
        if signal_strength >= 5 and signal_count >= 8:
            return "high"
        elif signal_strength >= 3 and signal_count >= 5:
            return "medium"
        elif signal_strength >= 1:
            return "low"
        else:
            return "very_low"

