"""
진입 분석기 (Entry Analyzer)

.. deprecated:: 4.4.0
    이 모듈은 레거시 코드입니다.
    새 코드에서는 AnalyzeBreakoutUseCase를 사용하세요.
    마이그레이션 가이드: docs/guide/MIGRATION_AI_CLEAN_ARCHITECTURE.md

포지션이 없을 때 사용하는 진입 전용 분석기입니다.
멀티코인 환경에서 여러 후보 중 최적의 진입 대상을 선정합니다.

역할:
- 변동성 돌파 전략 검증
- 진입 타이밍 판단
- 리스크 헌터 역할 (거래를 막을 이유 탐색)
"""
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
from openai import OpenAI

from ..config.settings import AIConfig
from ..utils.logger import Logger
from ..utils.helpers import safe_json_dumps


@dataclass
class EntrySignal:
    """진입 신호 데이터 클래스"""
    ticker: str
    decision: str  # 'buy', 'hold'
    confidence: str  # 'high', 'medium', 'low'
    score: float  # 종합 점수 (0-100)
    reason: str
    rejection_reasons: List[str]  # 거래를 막을 이유들
    key_indicators: List[str]
    backtest_grade: str  # 'STRONG PASS', 'WEAK PASS', 'FAIL'
    ai_used: bool = True


class EntryAnalyzer:
    """
    진입 분석기 클래스

    .. deprecated:: 4.4.0
        이 클래스는 레거시 코드입니다.
        새 코드에서는 AnalyzeBreakoutUseCase를 사용하세요.
        마이그레이션 가이드: docs/guide/MIGRATION_AI_CLEAN_ARCHITECTURE.md

    포지션이 없을 때만 사용됩니다.
    변동성 돌파 전략의 진입 조건을 AI로 검증합니다.
    """

    @staticmethod
    def _format_number(value: Any, format_str: str = ',.0f') -> str:
        """숫자 포맷팅 헬퍼"""
        if value == 'N/A' or value is None:
            return 'N/A'
        try:
            if isinstance(value, (int, float)):
                return f"{value:{format_str}}"
            return str(value)
        except (ValueError, TypeError):
            return 'N/A'

    def __init__(self):
        """진입 분석기 초기화"""
        self.client = OpenAI()
        self.model = AIConfig.MODEL

    def analyze_entry(
        self,
        ticker: str,
        analysis_data: Dict[str, Any],
        backtest_result: Optional[Dict] = None
    ) -> Optional[EntrySignal]:
        """
        단일 코인 진입 분석

        Args:
            ticker: 거래 종목 (예: "KRW-ETH")
            analysis_data: 분석 데이터 (차트, 지표, 오더북 등)
            backtest_result: 백테스팅 결과 (선택)

        Returns:
            EntrySignal: 진입 신호 또는 None
        """
        coin_symbol = ticker.split('-')[1]

        # 백테스팅 등급 판정
        backtest_grade, recommended_action, metrics = self._evaluate_backtest(
            backtest_result, analysis_data
        )

        # 시스템 프롬프트 생성 (리스크 헌터 역할)
        system_prompt = self._build_entry_system_prompt(
            coin_symbol, backtest_grade, recommended_action, metrics, analysis_data
        )

        # 사용자 프롬프트 생성
        user_prompt = self._build_entry_user_prompt(
            ticker, analysis_data, backtest_result
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )

            ai_response = response.choices[0].message.content
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            Logger.print_info(f"[{timestamp}] 진입 분석 중... ({ticker})")
            Logger.print_ai_response(timestamp, ai_response)

            decision_data = json.loads(ai_response)

            # 점수 계산
            score = self._calculate_entry_score(decision_data, backtest_grade)

            return EntrySignal(
                ticker=ticker,
                decision=decision_data.get("decision", "hold").lower(),
                confidence=decision_data.get("confidence", "medium"),
                score=score,
                reason=decision_data.get("reason", ""),
                rejection_reasons=decision_data.get("rejection_reasons", []),
                key_indicators=decision_data.get("key_indicators", []),
                backtest_grade=backtest_grade,
                ai_used=True
            )

        except json.JSONDecodeError as e:
            Logger.print_error(f"진입 분석 응답 파싱 실패: {str(e)}")
            return None
        except Exception as e:
            Logger.print_error(f"진입 분석 실패: {str(e)}")
            return None

    def analyze_multiple_entries(
        self,
        candidates: List[Dict[str, Any]],
        max_results: int = 3
    ) -> List[EntrySignal]:
        """
        여러 코인 진입 분석 (순차 실행)

        Args:
            candidates: 후보 코인 리스트 (ticker, analysis_data, backtest_result)
            max_results: 최대 반환 개수

        Returns:
            점수순 정렬된 진입 신호 리스트
        """
        results = []

        for candidate in candidates:
            ticker = candidate['ticker']
            analysis_data = candidate['analysis_data']
            backtest_result = candidate.get('backtest_result')

            Logger.print_info(f"📊 {ticker} 진입 분석 중...")

            signal = self.analyze_entry(ticker, analysis_data, backtest_result)
            if signal and signal.decision == 'buy':
                results.append(signal)

        # 점수순 정렬
        results.sort(key=lambda x: x.score, reverse=True)

        return results[:max_results]

    def _evaluate_backtest(
        self,
        backtest_result: Optional[Dict],
        analysis_data: Dict
    ) -> tuple:
        """백테스팅 결과 평가"""
        if not backtest_result:
            return "NO_DATA", "백테스팅 데이터 없음", {}

        metrics = backtest_result.get('metrics', {})
        total_return = metrics.get('total_return', 0)
        win_rate = metrics.get('win_rate', 0)
        sharpe = metrics.get('sharpe_ratio', 0)
        profit_factor = metrics.get('profit_factor', 0)

        # 동적 임계값 (시장 변동성 대비)
        risk_metrics = analysis_data.get('risk_metrics', {})
        market_volatility = risk_metrics.get('volatility_30d', 30)
        volatility_adjustment = 30 / max(market_volatility, 10)

        adjusted_return_threshold = 5 * volatility_adjustment
        adjusted_sharpe_threshold = 0.5 * volatility_adjustment

        # BTC 대비 Alpha 계산
        market_corr = analysis_data.get('market_correlation', {})
        btc_perf = market_corr.get('btc_performance', {})
        btc_return_30d = btc_perf.get('return_30d', 0) if btc_perf else 0
        alpha = total_return - btc_return_30d

        if total_return > adjusted_return_threshold and win_rate > 40 and sharpe > adjusted_sharpe_threshold:
            grade = "STRONG PASS"
            action = f"백테스팅 양호 (Alpha: {alpha:+.2f}%). 진입 검토 가능."
        elif total_return > adjusted_return_threshold * 0.6 and win_rate > 35:
            grade = "WEAK PASS"
            action = f"전략 성과 약화 중 (Alpha: {alpha:+.2f}%). 신중한 접근 필요."
        else:
            grade = "FAIL"
            action = f"전략 부진 (Alpha: {alpha:+.2f}%). 진입 재검토 필요."

        return grade, action, {
            'total_return': total_return,
            'win_rate': win_rate,
            'sharpe': sharpe,
            'profit_factor': profit_factor,
            'alpha': alpha,
            'volatility_adjustment': volatility_adjustment,
            'adjusted_return_threshold': adjusted_return_threshold,
            'adjusted_sharpe_threshold': adjusted_sharpe_threshold
        }

    def _build_entry_system_prompt(
        self,
        coin_symbol: str,
        backtest_grade: str,
        recommended_action: str,
        metrics: Dict,
        analysis_data: Dict
    ) -> str:
        """진입 분석용 시스템 프롬프트 생성"""

        risk_metrics = analysis_data.get('risk_metrics', {})
        market_volatility = risk_metrics.get('volatility_30d', 30)
        volatility_adjustment = metrics.get('volatility_adjustment', 1.0)

        return f"""당신은 **리스크 헌터(Risk Hunter)** 역할의 트레이딩 검증자입니다.
당신의 임무는 이 거래를 **막을 이유를 적극적으로 찾는 것**입니다.
설득력 있는 이유가 없을 때만 거래를 승인하세요.

## 현재 상황: 신규 진입 검토
- 코인: {coin_symbol}
- 포지션 상태: 없음 (신규 진입 검토 중)
- 전략: 변동성 돌파 (Volatility Breakout)

## ⚠️ 중요 경고:
- **과거 성과가 미래를 보장하지 않습니다.**
- 백테스팅이 양호해도 시장 국면(Regime) 변화 시 성과가 꺾일 수 있습니다.
- 당신은 '거수기'가 아닙니다. **비판적 시각**을 유지하세요.

## 백테스팅 성과 (최근 30일):
- 총 수익률: {self._format_number(metrics.get('total_return', 0), '.2f')}%
- BTC 대비 Alpha: {self._format_number(metrics.get('alpha', 0), '+.2f')}%
- 승률: {self._format_number(metrics.get('win_rate', 0), '.2f')}%
- Sharpe Ratio: {self._format_number(metrics.get('sharpe', 0), '.2f')}
- 시장 변동성: {self._format_number(market_volatility, '.1f')}%
- 임계값 조정: {self._format_number(volatility_adjustment, '.2f')}x
→ **등급: {backtest_grade}** - {recommended_action}

## 🎯 핵심 임무: 이 거래를 막을 이유 3가지를 찾으세요
1. **시장 국면 변화**: ATR, 거래량, 변동성 패턴이 최근 30일과 다른가?
2. **모멘텀 약화 신호**: RSI 다이버전스, 거래량 감소 등
3. **구조적 위험**: 저항선 근접, 오더북 불균형, BTC 약세 등

## ✅ 안전 조건 (모두 충족해야 진입):
1. 오더북 안전: 매도벽 비율 < 5%
2. 추세 명확: ADX > 25
3. 거래량 확인: 현재 거래량 > 평균의 1.5배
4. 볼린저 밴드: 상단 터치 후 즉시 하락 패턴 아님
5. Regime 일관성: 현재 시장 환경이 최근 30일과 유사

## ⚠️ 위험 조건 (하나라도 있으면 HOLD):
1. BTC 급락 위험: market_risk='high'
2. RSI 다이버전스: 가격↑ but RSI↓
3. 플래시 크래시 감지
4. 극단적 탐욕: 공포탐욕지수 > 75
5. 거래량-가격 괴리
6. Alpha 음수: BTC 대비 언더퍼폼

## 판단 기준:
- **BUY**: 안전 조건 모두 충족 AND 위험 조건 없음 AND 막을 이유 없음
- **HOLD**: 안전 조건 미충족 OR 위험 조건 존재 OR 막을 이유 1개 이상

## 출력 형식 (한국어 JSON):
{{
  "decision": "buy|hold",
  "reason": "상세 분석 (한국어)",
  "confidence": "high|medium|low",
  "rejection_reasons": ["거래를 막을 이유 리스트"],
  "safety_conditions_met": {{"orderbook": true/false, "trend": true/false, "volume": true/false}},
  "risk_conditions_detected": {{"btc_risk": true/false, "rsi_divergence": true/false}},
  "key_indicators": ["주요 지표 리스트"]
}}"""

    def _build_entry_user_prompt(
        self,
        ticker: str,
        analysis_data: Dict,
        backtest_result: Optional[Dict]
    ) -> str:
        """진입 분석용 사용자 프롬프트 생성"""

        # 변동성 돌파 룰 통과 정보
        rule_info = analysis_data.get('rule_breakout', {})
        is_breakout = rule_info.get('passed', False)

        prompt = f"""## 진입 분석 요청: {ticker}

### 변동성 돌파 전략 상태:
- 룰 통과 여부: {'✅ 통과' if is_breakout else '❌ 미통과'}
"""
        if is_breakout:
            prompt += f"""- 관문 1 (응축): {rule_info.get('gate1', 'N/A')}
- 관문 2 (돌파): {rule_info.get('gate2', 'N/A')}
- 관문 3 (거래량): {rule_info.get('gate3', 'N/A')}

**중요**: 위 룰을 통과했지만, Fakeout(속임수)일 수 있습니다.
"""

        # 현재 상태
        current_status = analysis_data.get('current_status', {})
        prompt += f"""
### 현재 상태:
- KRW 잔고: {current_status.get('krw_balance', 0):,.0f} KRW
- 현재가: {current_status.get('current_price', 0):,.0f} KRW
"""

        # 기술적 지표
        if 'technical_indicators' in analysis_data:
            prompt += f"""
### 기술적 지표:
{safe_json_dumps(analysis_data['technical_indicators'])}
"""

        # 오더북
        if 'orderbook_summary' in analysis_data:
            prompt += f"""
### 오더북:
{safe_json_dumps(analysis_data['orderbook_summary'])}
"""

        # 리스크 메트릭스
        if 'risk_metrics' in analysis_data:
            risk = analysis_data['risk_metrics']
            prompt += f"""
### 리스크 지표:
- Sharpe Ratio: {self._format_number(risk.get('sharpe_ratio'), '.2f')}
- Max Drawdown: {self._format_number(risk.get('max_drawdown'), '.2f')}%
- 30일 Volatility: {self._format_number(risk.get('volatility_30d'), '.2f')}%
"""

        # 공포탐욕지수
        if 'fear_greed_index' in analysis_data:
            fgi = analysis_data['fear_greed_index']
            prompt += f"""
### 공포탐욕지수:
- 값: {fgi.get('value', 'N/A')}/100 ({fgi.get('classification', 'N/A')})
"""

        # 시장 상관관계
        if 'market_correlation' in analysis_data:
            corr = analysis_data['market_correlation']
            prompt += f"""
### 시장 상관관계:
- BTC 상관계수: {self._format_number(corr.get('btc_correlation'), '.2f')}
- 시장 리스크: {corr.get('market_risk', 'N/A')}
"""

        # 백테스팅 결과
        if backtest_result:
            metrics = backtest_result.get('metrics', {})
            prompt += f"""
### 백테스팅 결과 (최근 30일):
- 총 수익률: {self._format_number(metrics.get('total_return'), '.2f')}%
- 승률: {self._format_number(metrics.get('win_rate'), '.2f')}%
- Sharpe: {self._format_number(metrics.get('sharpe_ratio'), '.2f')}
- 통과 여부: {backtest_result.get('passed', False)}
"""

        prompt += """
### 분석 요청:
위 데이터를 바탕으로 신규 진입 여부를 판단하세요.
반드시 한국어 JSON 형식으로 응답하세요."""

        return prompt

    def _calculate_entry_score(
        self,
        decision_data: Dict,
        backtest_grade: str
    ) -> float:
        """진입 신호 종합 점수 계산 (0-100)"""
        score = 50.0  # 기본 점수

        # 1. AI 판단 반영 (±20)
        if decision_data.get('decision', '').lower() == 'buy':
            score += 15
        else:
            score -= 20

        # 2. 신뢰도 반영 (±10)
        confidence = decision_data.get('confidence', 'medium').lower()
        if confidence == 'high':
            score += 10
        elif confidence == 'low':
            score -= 10

        # 3. 백테스팅 등급 반영 (±15)
        if backtest_grade == 'STRONG PASS':
            score += 15
        elif backtest_grade == 'WEAK PASS':
            score += 5
        elif backtest_grade == 'FAIL':
            score -= 15

        # 4. 거부 이유 개수 반영 (-5 per reason)
        rejection_count = len(decision_data.get('rejection_reasons', []))
        score -= rejection_count * 5

        # 5. 안전 조건 충족 반영 (+3 per condition)
        safety = decision_data.get('safety_conditions_met', {})
        safety_count = sum(1 for v in safety.values() if v is True)
        score += safety_count * 3

        # 6. 위험 조건 감지 반영 (-8 per risk)
        risks = decision_data.get('risk_conditions_detected', {})
        risk_count = sum(1 for v in risks.values() if v is True)
        score -= risk_count * 8

        # 범위 제한
        return max(0.0, min(100.0, score))
