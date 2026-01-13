"""
MLOptimizationRunner - ML 최적화 파이프라인 실행기

실제 백테스팅 엔진과 ML 옵티마이저를 연결하여
프로덕션 수준의 필터 최적화를 수행한다.
"""

import logging
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import pandas as pd
import numpy as np

from src.domain.value_objects.cost_policy import CostPolicy
from src.ml.data_loader import MLDataLoader
from src.ml.search_space import SearchSpace
from src.ml.objective_function import ProductionObjectiveFunction
from src.ml.constraints import Constraints
from src.backtesting.quick_filter import QuickBacktestFilter, BacktestConfig

logger = logging.getLogger(__name__)


@dataclass
class OptimizationConfig:
    """
    최적화 설정

    Attributes:
        n_random_trials: Stage 1 Random Search 시도 횟수
        n_bayesian_trials: Stage 2 Bayesian Search 시도 횟수
        cost_policy: 비용 정책
        backtest_days: 백테스트 기간 (일)
        min_data_rows: 최소 데이터 행 수
    """
    n_random_trials: int = 50
    n_bayesian_trials: int = 100
    cost_policy: CostPolicy = field(default_factory=CostPolicy.default)
    backtest_days: int = 365
    min_data_rows: int = 200


class MLOptimizationRunner:
    """
    ML 필터 최적화 실행기

    실제 백테스팅 엔진(QuickBacktestFilter)과 연동하여
    필터 설정을 최적화한다.
    """

    def __init__(
        self,
        config: OptimizationConfig = None,
        data_dir: str = "data/historical",
        output_dir: str = "data/ml_results",
    ):
        """
        Args:
            config: 최적화 설정
            data_dir: 데이터 디렉토리
            output_dir: 결과 저장 디렉토리
        """
        self.config = config or OptimizationConfig()
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 데이터 로더
        self.data_loader = MLDataLoader(str(data_dir))

        # Search Space
        self.search_space = SearchSpace()

        # Objective Function
        self.objective_fn = ProductionObjectiveFunction(self.config.cost_policy)

        # 캐시
        self._data_cache: Dict[str, pd.DataFrame] = {}
        self._result_cache: Dict[str, Dict] = {}

        logger.info(f"MLOptimizationRunner 초기화 완료")
        logger.info(f"  - Random trials: {self.config.n_random_trials}")
        logger.info(f"  - Bayesian trials: {self.config.n_bayesian_trials}")
        logger.info(f"  - Backtest days: {self.config.backtest_days}")

    def load_data(self) -> Dict[str, pd.DataFrame]:
        """
        히스토리컬 데이터 로드

        Returns:
            {ticker: DataFrame} 딕셔너리
        """
        if self._data_cache:
            logger.info("캐시된 데이터 사용")
            return self._data_cache

        data_dict = self.data_loader.load_all_tickers(
            min_rows=self.config.min_data_rows
        )

        self._data_cache = data_dict

        # 데이터 요약 출력
        summary = self.data_loader.get_data_summary()
        logger.info("=" * 60)
        logger.info("📊 데이터 로드 완료")
        for ticker, info in summary.items():
            if ticker in data_dict:
                logger.info(
                    f"  {ticker}: {info['rows']}일 "
                    f"({info['start']} ~ {info['end']}, {info['years']}년)"
                )
        logger.info("=" * 60)

        return data_dict

    def run_backtest_with_config(
        self,
        ticker: str,
        data: pd.DataFrame,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        특정 Config로 백테스트 실행

        Args:
            ticker: 티커 심볼
            data: OHLCV 데이터
            config: 필터 설정

        Returns:
            백테스트 결과 메트릭
        """
        # BacktestConfig 생성
        backtest_config = BacktestConfig(
            days=len(data),
            use_local_data=False,  # 직접 데이터 전달
            min_return=config.get('thresholds', {}).get('min_return', 9.0),
            min_sharpe_ratio=config.get('thresholds', {}).get('min_sharpe_ratio', 0.7),
            min_profit_factor=config.get('thresholds', {}).get('min_profit_factor', 1.5),
            min_trades=config.get('thresholds', {}).get('min_trades', 30),
            max_drawdown=config.get('thresholds', {}).get('max_drawdown', 25.0),
            use_weighted_evaluation=True,
        )

        # QuickBacktestFilter 실행
        filter_obj = QuickBacktestFilter(config=backtest_config)

        # Upbit 형식 티커로 변환
        upbit_ticker = self.data_loader.convert_to_upbit_format(ticker)

        # 차트 데이터 구성
        chart_data = {'day': data}

        result = filter_obj.run_quick_backtest(
            ticker=upbit_ticker,
            chart_data=chart_data,
        )

        if result.result is None:
            return {
                'passed': False,
                'total_return': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'total_trades': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
            }

        # 메트릭 추출
        metrics = result.metrics
        metrics['passed'] = result.passed
        metrics['filter_results'] = result.filter_results

        # 비용 적용
        if 'total_return' in metrics:
            gross_return = metrics['total_return'] / 100.0  # % → 비율
            order_size = 100_000_000  # 1억
            daily_volume = data['volume'].mean() * data['close'].mean()
            volatility = data['close'].pct_change().std()

            net_return = self.config.cost_policy.calculate_total_cost(
                gross_return=gross_return,
                order_size=order_size,
                daily_volume=daily_volume,
                volatility=volatility,
            )
            metrics['net_return'] = (gross_return - net_return) * 100  # 비율 → %

        return metrics

    def evaluate_config(
        self,
        config: Dict[str, Any],
        tickers: Optional[List[str]] = None,
    ) -> float:
        """
        Config 평가 (여러 티커에 대해 백테스트 후 점수 계산)

        Args:
            config: 필터 설정
            tickers: 평가할 티커 (None이면 전체)

        Returns:
            목적 함수 점수
        """
        data_dict = self.load_data()

        if tickers is None:
            tickers = list(data_dict.keys())

        results = []
        passed_count = 0

        for ticker in tickers:
            if ticker not in data_dict:
                continue

            data = data_dict[ticker]
            metrics = self.run_backtest_with_config(ticker, data, config)

            if metrics.get('passed', False):
                passed_count += 1

            # Objective function용 결과 구성
            result = {
                'gross_return': metrics.get('total_return', 0) / 100.0,
                'sharpe_ratio': metrics.get('sharpe_ratio', 0),
                'max_drawdown': abs(metrics.get('max_drawdown', 0)) / 100.0,
                'total_trades': metrics.get('total_trades', 0),
                'daily_volume': data['volume'].mean() * data['close'].mean(),
                'volatility': data['close'].pct_change().std(),
                'pass_rate': 1.0 if metrics.get('passed', False) else 0.0,
            }
            results.append(result)

        if not results:
            return 0.0

        # Pass rate 추가
        avg_result = {
            'gross_return': np.mean([r['gross_return'] for r in results]),
            'sharpe_ratio': np.mean([r['sharpe_ratio'] for r in results]),
            'max_drawdown': np.mean([r['max_drawdown'] for r in results]),
            'total_trades': np.mean([r['total_trades'] for r in results]),
            'daily_volume': np.mean([r['daily_volume'] for r in results]),
            'volatility': np.mean([r['volatility'] for r in results]),
            'pass_rate': passed_count / len(tickers),
        }

        score = self.objective_fn.evaluate([avg_result])

        return score

    def random_search(self, n_trials: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Stage 1: Random Search

        Args:
            n_trials: 시도 횟수

        Returns:
            점수 내림차순 정렬된 결과
        """
        n_trials = n_trials or self.config.n_random_trials
        results = []

        logger.info(f"🔍 Stage 1: Random Search ({n_trials} trials)")

        for i in range(n_trials):
            config = self.search_space.sample_config()
            score = self.evaluate_config(config)

            results.append({
                'config': config,
                'score': score,
                'trial': i,
                'stage': 1,
            })

            if (i + 1) % 10 == 0:
                best_so_far = max(r['score'] for r in results)
                logger.info(f"  Trial {i+1}/{n_trials}: best={best_so_far:.4f}")

        results.sort(key=lambda x: x['score'], reverse=True)

        logger.info(f"✅ Random Search 완료: best={results[0]['score']:.4f}")
        return results

    def bayesian_search(
        self,
        warm_start: Optional[List[Dict[str, Any]]] = None,
        n_trials: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Stage 2: Bayesian Search (Gaussian Perturbation)

        Args:
            warm_start: Stage 1 상위 결과
            n_trials: 시도 횟수

        Returns:
            점수 내림차순 정렬된 결과
        """
        n_trials = n_trials or self.config.n_bayesian_trials
        results = []

        logger.info(f"🧠 Stage 2: Bayesian Search ({n_trials} trials)")

        # Base configs from warm start
        if warm_start:
            base_configs = [r['config'] for r in warm_start]
        else:
            base_configs = [self.search_space.sample_config()]

        for i in range(n_trials):
            # 기존 좋은 config를 perturbation
            base = base_configs[i % len(base_configs)]
            config = self._perturb_config(base, noise_scale=0.15)
            score = self.evaluate_config(config)

            results.append({
                'config': config,
                'score': score,
                'trial': i,
                'stage': 2,
            })

            # 좋은 결과를 base에 추가
            if score > np.median([r['score'] for r in results]):
                base_configs.append(config)

            if (i + 1) % 20 == 0:
                best_so_far = max(r['score'] for r in results)
                logger.info(f"  Trial {i+1}/{n_trials}: best={best_so_far:.4f}")

        results.sort(key=lambda x: x['score'], reverse=True)

        logger.info(f"✅ Bayesian Search 완료: best={results[0]['score']:.4f}")
        return results

    def run_optimization(self) -> Dict[str, Any]:
        """
        전체 최적화 파이프라인 실행

        Returns:
            최적화 결과
        """
        start_time = datetime.now()
        logger.info("=" * 60)
        logger.info("🚀 ML Filter Optimization 시작")
        logger.info(f"  시작 시간: {start_time}")
        logger.info("=" * 60)

        # 데이터 로드
        self.load_data()

        # Stage 1: Random Search
        stage1_results = self.random_search()

        # 상위 10% warm start
        top_percent = max(1, len(stage1_results) // 10)
        warm_start = stage1_results[:top_percent]

        # Stage 2: Bayesian Search
        stage2_results = self.bayesian_search(warm_start=warm_start)

        # 최적 결과 선택
        all_results = stage1_results + stage2_results
        all_results.sort(key=lambda x: x['score'], reverse=True)

        best_result = all_results[0]

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # 결과 저장
        optimization_result = {
            'timestamp': start_time.isoformat(),
            'duration_seconds': duration,
            'n_random_trials': self.config.n_random_trials,
            'n_bayesian_trials': self.config.n_bayesian_trials,
            'best_config': best_result['config'],
            'best_score': best_result['score'],
            'stage1_best': stage1_results[0]['score'] if stage1_results else 0,
            'stage2_best': stage2_results[0]['score'] if stage2_results else 0,
            'top_5_configs': [
                {
                    'config': r['config'],
                    'score': r['score'],
                    'stage': r['stage'],
                }
                for r in all_results[:5]
            ],
        }

        # 파일 저장
        self._save_results(optimization_result)

        logger.info("=" * 60)
        logger.info("🎉 ML Filter Optimization 완료")
        logger.info(f"  소요 시간: {duration:.1f}초")
        logger.info(f"  최적 점수: {best_result['score']:.4f}")
        logger.info(f"  최적 threshold_ratio: {best_result['config']['threshold_ratio']:.3f}")
        logger.info("=" * 60)

        return optimization_result

    def _perturb_config(
        self,
        config: Dict[str, Any],
        noise_scale: float = 0.1,
    ) -> Dict[str, Any]:
        """
        Config에 Gaussian perturbation 적용

        Args:
            config: 원본 Config
            noise_scale: 노이즈 스케일

        Returns:
            Perturbation된 Config
        """
        import random

        new_config = {
            'threshold_ratio': np.clip(
                config['threshold_ratio'] + random.gauss(0, noise_scale * 0.1),
                0.50, 0.85
            ),
            'filter_weights': {},
            'thresholds': dict(config.get('thresholds', {})),
            'tier1_filters': set(config.get('tier1_filters', {'return', 'sharpe_ratio'})),
        }

        for key, value in config.get('filter_weights', {}).items():
            if key in self.search_space.WEIGHT_RANGES:
                min_val, max_val = self.search_space.WEIGHT_RANGES[key]
                new_value = np.clip(
                    value + random.gauss(0, noise_scale * (max_val - min_val)),
                    min_val, max_val
                )
                new_config['filter_weights'][key] = new_value

        return new_config

    def _save_results(self, result: Dict[str, Any]) -> None:
        """
        결과를 파일로 저장

        Args:
            result: 최적화 결과
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"optimization_result_{timestamp}.json"
        filepath = self.output_dir / filename

        # tier1_filters set → list 변환
        serializable_result = self._make_serializable(result)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(serializable_result, f, indent=2, ensure_ascii=False)

        logger.info(f"결과 저장: {filepath}")

    def _make_serializable(self, obj: Any) -> Any:
        """
        JSON 직렬화 가능하도록 변환

        Args:
            obj: 변환할 객체

        Returns:
            직렬화 가능한 객체
        """
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(v) for v in obj]
        elif isinstance(obj, set):
            return list(obj)
        elif isinstance(obj, (np.floating, np.integer)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return obj
