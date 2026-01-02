#!/usr/bin/env python3
"""
롤링 백테스트 스크립트

목적: 시계열 안정성 검증, 과최적화 방지

롤링 백테스트는 동일한 전략을 여러 시간대에 적용하여
성과의 일관성을 검증합니다. 이를 통해:
1. 과최적화 여부 확인 (특정 기간에만 잘 작동하는지)
2. 전략의 시장 환경 적응력 평가
3. 성과 지표의 분산 측정

사용법:
    python scripts/rolling_backtest.py --ticker KRW-BTC --window 6 --step 1

작성일: 2026-01-02
"""
import sys
import os
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backtesting.backtester import Backtester
from src.backtesting.rule_based_strategy import RuleBasedBreakoutStrategy
from src.backtesting.performance import PerformanceAnalyzer
from src.data.collector import DataCollector
from src.config.settings import TradingConfig


class RollingBacktester:
    """
    롤링 백테스트 실행기

    지정된 기간 동안 윈도우를 이동하면서
    동일한 전략의 성과를 측정합니다.
    """

    def __init__(
        self,
        ticker: str,
        window_months: int = 6,
        step_months: int = 1,
        initial_capital: float = 10_000_000,
        commission: float = 0.0005,
        slippage: float = 0.001,
        data_interval: str = 'day'
    ):
        """
        Args:
            ticker: 거래 종목 (예: 'KRW-BTC')
            window_months: 백테스트 윈도우 크기 (월)
            step_months: 윈도우 이동 간격 (월)
            initial_capital: 초기 자본
            commission: 수수료율
            slippage: 슬리피지율
            data_interval: 데이터 간격 ('day', 'minute60', 등)
        """
        self.ticker = ticker
        self.window_months = window_months
        self.step_months = step_months
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.data_interval = data_interval

        self.results: List[Dict[str, Any]] = []

    def run(
        self,
        data: pd.DataFrame,
        strategy_params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        롤링 백테스트 실행

        Args:
            data: 전체 OHLCV 데이터 (DatetimeIndex 필요)
            strategy_params: 전략 파라미터 (옵션)

        Returns:
            각 구간별 성과 지표 리스트
        """
        if strategy_params is None:
            strategy_params = {}

        # 데이터 유효성 검사
        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("데이터에 DatetimeIndex가 필요합니다")

        self.results = []
        start_date = data.index[0]
        end_date = data.index[-1]

        print(f"\n{'='*60}")
        print(f"롤링 백테스트 시작")
        print(f"{'='*60}")
        print(f"종목: {self.ticker}")
        print(f"전체 기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
        print(f"윈도우: {self.window_months}개월, 스텝: {self.step_months}개월")
        print(f"초기 자본: {self.initial_capital:,.0f}원")
        print(f"{'='*60}\n")

        current_start = start_date
        window_count = 0

        while True:
            # 윈도우 종료일 계산
            current_end = current_start + pd.DateOffset(months=self.window_months)

            # 종료일이 데이터 범위를 초과하면 중단
            if current_end > end_date:
                break

            # 구간 데이터 추출
            window_data = data.loc[current_start:current_end].copy()

            if len(window_data) < 30:  # 최소 30일 필요
                current_start += pd.DateOffset(months=self.step_months)
                continue

            window_count += 1
            print(f"\n[윈도우 {window_count}] {current_start.strftime('%Y-%m-%d')} ~ {current_end.strftime('%Y-%m-%d')}")
            print(f"  데이터 포인트: {len(window_data)}개")

            # 전략 생성 (매 윈도우마다 새로 생성)
            strategy = RuleBasedBreakoutStrategy(
                ticker=self.ticker,
                **strategy_params
            )

            # 백테스터 생성 및 실행
            backtester = Backtester(
                strategy=strategy,
                data=window_data,
                ticker=self.ticker,
                initial_capital=self.initial_capital,
                commission=self.commission,
                slippage=self.slippage,
                execute_on_next_open=True,
                data_interval=self.data_interval
            )

            try:
                result = backtester.run()

                # 결과 저장
                window_result = {
                    'window_number': window_count,
                    'start_date': current_start,
                    'end_date': current_end,
                    'data_points': len(window_data),
                    'total_return': result.metrics.get('total_return', 0),
                    'max_drawdown': result.metrics.get('max_drawdown', 0),
                    'sharpe_ratio': result.metrics.get('sharpe_ratio', 0),
                    'sortino_ratio': result.metrics.get('sortino_ratio', 0),
                    'win_rate': result.metrics.get('win_rate', 0),
                    'profit_factor': result.metrics.get('profit_factor', 0),
                    'total_trades': result.metrics.get('total_trades', 0),
                    'avg_holding_period_hours': result.metrics.get('avg_holding_period_hours', 0),
                    'final_equity': result.final_equity,
                    'max_consecutive_wins': result.metrics.get('max_consecutive_wins', 0),
                    'max_consecutive_losses': result.metrics.get('max_consecutive_losses', 0),
                }
                self.results.append(window_result)

                # 결과 출력
                print(f"  수익률: {window_result['total_return']:.2f}%")
                print(f"  MDD: {window_result['max_drawdown']:.2f}%")
                print(f"  샤프: {window_result['sharpe_ratio']:.2f}")
                print(f"  승률: {window_result['win_rate']:.1f}%")
                print(f"  거래수: {window_result['total_trades']}회")

            except Exception as e:
                print(f"  ⚠️ 백테스트 실패: {str(e)}")
                self.results.append({
                    'window_number': window_count,
                    'start_date': current_start,
                    'end_date': current_end,
                    'error': str(e)
                })

            # 다음 윈도우로 이동
            current_start += pd.DateOffset(months=self.step_months)

        print(f"\n{'='*60}")
        print(f"롤링 백테스트 완료: {window_count}개 윈도우 테스트")
        print(f"{'='*60}")

        return self.results

    def get_summary(self) -> Dict[str, Any]:
        """
        롤링 백테스트 요약 통계 계산

        Returns:
            요약 통계 딕셔너리
        """
        if not self.results:
            return {'error': '결과 없음'}

        # 에러가 없는 결과만 필터링
        valid_results = [r for r in self.results if 'error' not in r]

        if not valid_results:
            return {'error': '유효한 결과 없음'}

        # 각 지표별 통계 계산
        returns = [r['total_return'] for r in valid_results]
        mdds = [r['max_drawdown'] for r in valid_results]
        sharpes = [r['sharpe_ratio'] for r in valid_results]
        win_rates = [r['win_rate'] for r in valid_results]
        profit_factors = [r['profit_factor'] for r in valid_results if r['profit_factor'] != float('inf')]

        summary = {
            'total_windows': len(self.results),
            'valid_windows': len(valid_results),
            'failed_windows': len(self.results) - len(valid_results),

            # 수익률 통계
            'return_mean': np.mean(returns),
            'return_std': np.std(returns),
            'return_min': np.min(returns),
            'return_max': np.max(returns),
            'return_median': np.median(returns),
            'positive_return_ratio': sum(1 for r in returns if r > 0) / len(returns) * 100,

            # MDD 통계
            'mdd_mean': np.mean(mdds),
            'mdd_worst': np.min(mdds),  # 가장 큰 MDD (음수이므로 min)
            'mdd_best': np.max(mdds),

            # 샤프 비율 통계
            'sharpe_mean': np.mean(sharpes),
            'sharpe_std': np.std(sharpes),
            'sharpe_min': np.min(sharpes),
            'sharpe_max': np.max(sharpes),

            # 승률 통계
            'win_rate_mean': np.mean(win_rates),
            'win_rate_std': np.std(win_rates),

            # Profit Factor 통계
            'profit_factor_mean': np.mean(profit_factors) if profit_factors else 0,
            'profit_factor_median': np.median(profit_factors) if profit_factors else 0,

            # 일관성 지표
            'consistency_score': self._calculate_consistency_score(valid_results),
        }

        return summary

    def _calculate_consistency_score(self, results: List[Dict]) -> float:
        """
        전략 일관성 점수 계산 (0-100)

        점수 기준:
        - 수익률 일관성 (표준편차 낮을수록 좋음)
        - 양의 수익 비율
        - 샤프 비율 일관성
        """
        if not results:
            return 0

        returns = [r['total_return'] for r in results]
        sharpes = [r['sharpe_ratio'] for r in results]

        # 1. 양의 수익 비율 (최대 40점)
        positive_ratio = sum(1 for r in returns if r > 0) / len(returns)
        positive_score = positive_ratio * 40

        # 2. 수익률 표준편차 점수 (최대 30점)
        # 표준편차가 낮을수록 좋음 (10% 이하면 만점)
        return_std = np.std(returns)
        std_score = max(0, 30 - (return_std / 10) * 30)

        # 3. 평균 샤프 비율 점수 (최대 30점)
        # 샤프 1.0 이상이면 만점
        avg_sharpe = np.mean(sharpes)
        sharpe_score = min(30, avg_sharpe * 30)

        total_score = positive_score + std_score + sharpe_score
        return round(total_score, 1)

    def print_summary(self) -> None:
        """요약 통계 출력"""
        summary = self.get_summary()

        if 'error' in summary:
            print(f"\n⚠️ {summary['error']}")
            return

        print(f"\n{'='*60}")
        print("📊 롤링 백테스트 요약")
        print(f"{'='*60}")

        print(f"\n[윈도우 정보]")
        print(f"  전체 윈도우: {summary['total_windows']}개")
        print(f"  유효 윈도우: {summary['valid_windows']}개")
        print(f"  실패 윈도우: {summary['failed_windows']}개")

        print(f"\n[수익률 통계]")
        print(f"  평균: {summary['return_mean']:.2f}%")
        print(f"  표준편차: {summary['return_std']:.2f}%")
        print(f"  최소: {summary['return_min']:.2f}%")
        print(f"  최대: {summary['return_max']:.2f}%")
        print(f"  중앙값: {summary['return_median']:.2f}%")
        print(f"  양의 수익 비율: {summary['positive_return_ratio']:.1f}%")

        print(f"\n[MDD 통계]")
        print(f"  평균: {summary['mdd_mean']:.2f}%")
        print(f"  최악: {summary['mdd_worst']:.2f}%")
        print(f"  최선: {summary['mdd_best']:.2f}%")

        print(f"\n[리스크 조정 수익률]")
        print(f"  평균 샤프: {summary['sharpe_mean']:.2f}")
        print(f"  샤프 표준편차: {summary['sharpe_std']:.2f}")
        print(f"  샤프 범위: {summary['sharpe_min']:.2f} ~ {summary['sharpe_max']:.2f}")

        print(f"\n[거래 통계]")
        print(f"  평균 승률: {summary['win_rate_mean']:.1f}%")
        print(f"  평균 Profit Factor: {summary['profit_factor_mean']:.2f}")

        print(f"\n[일관성 점수]")
        consistency = summary['consistency_score']
        if consistency >= 70:
            rating = "✅ 우수"
        elif consistency >= 50:
            rating = "⚠️ 보통"
        else:
            rating = "❌ 미흡"
        print(f"  점수: {consistency}/100 ({rating})")

        print(f"\n{'='*60}")

    def export_results(self, output_path: str) -> None:
        """결과를 CSV로 내보내기"""
        if not self.results:
            print("내보낼 결과가 없습니다")
            return

        df = pd.DataFrame(self.results)
        df.to_csv(output_path, index=False)
        print(f"\n결과 저장: {output_path}")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='롤링 백테스트 실행')
    parser.add_argument('--ticker', type=str, default='KRW-BTC', help='거래 종목')
    parser.add_argument('--window', type=int, default=6, help='윈도우 크기 (월)')
    parser.add_argument('--step', type=int, default=1, help='스텝 크기 (월)')
    parser.add_argument('--capital', type=float, default=10_000_000, help='초기 자본')
    parser.add_argument('--output', type=str, default=None, help='결과 저장 경로')
    parser.add_argument('--days', type=int, default=365, help='데이터 조회 기간 (일)')

    args = parser.parse_args()

    print(f"\n데이터 수집 중: {args.ticker} ({args.days}일)...")

    try:
        # 데이터 수집
        collector = DataCollector()
        data = collector.collect_ohlcv_data(
            ticker=args.ticker,
            interval='day',
            count=args.days
        )

        if data is None or len(data) < 60:
            print(f"⚠️ 데이터 부족: {len(data) if data is not None else 0}일")
            return

        print(f"데이터 수집 완료: {len(data)}일")

        # 롤링 백테스트 실행
        rolling_bt = RollingBacktester(
            ticker=args.ticker,
            window_months=args.window,
            step_months=args.step,
            initial_capital=args.capital,
            commission=TradingConfig.FEE_RATE,
            slippage=0.001
        )

        rolling_bt.run(data)
        rolling_bt.print_summary()

        # 결과 저장
        if args.output:
            rolling_bt.export_results(args.output)
        else:
            # 기본 저장 경로
            output_path = f"data/rolling_backtest_{args.ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            os.makedirs("data", exist_ok=True)
            rolling_bt.export_results(output_path)

    except Exception as e:
        print(f"⚠️ 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
