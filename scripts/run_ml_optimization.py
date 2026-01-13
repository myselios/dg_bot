#!/usr/bin/env python3
"""
ML Filter Optimization CLI

사용법:
    python scripts/run_ml_optimization.py [옵션]

옵션:
    --random-trials N    Random Search 시도 횟수 (기본: 30)
    --bayesian-trials N  Bayesian Search 시도 횟수 (기본: 50)
    --quick              빠른 테스트 모드 (각 10회)
    --full               전체 최적화 (각 100, 200회)
    --data-dir PATH      데이터 디렉토리 (기본: data/historical)
    --output-dir PATH    결과 저장 디렉토리 (기본: data/ml_results)

예시:
    # 빠른 테스트
    python scripts/run_ml_optimization.py --quick

    # 전체 최적화
    python scripts/run_ml_optimization.py --full

    # 커스텀 설정
    python scripts/run_ml_optimization.py --random-trials 50 --bayesian-trials 100
"""

import sys
import argparse
import logging
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.domain.value_objects.cost_policy import CostPolicy
from src.ml.optimization_runner import MLOptimizationRunner, OptimizationConfig


def setup_logging(verbose: bool = False) -> None:
    """로깅 설정"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )


def parse_args() -> argparse.Namespace:
    """명령줄 인자 파싱"""
    parser = argparse.ArgumentParser(
        description='ML Filter Optimization CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # 모드 선택
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        '--quick',
        action='store_true',
        help='빠른 테스트 모드 (각 10회)',
    )
    mode_group.add_argument(
        '--full',
        action='store_true',
        help='전체 최적화 모드 (각 100, 200회)',
    )

    # 커스텀 설정
    parser.add_argument(
        '--random-trials',
        type=int,
        default=30,
        help='Random Search 시도 횟수 (기본: 30)',
    )
    parser.add_argument(
        '--bayesian-trials',
        type=int,
        default=50,
        help='Bayesian Search 시도 횟수 (기본: 50)',
    )

    # 디렉토리
    parser.add_argument(
        '--data-dir',
        type=str,
        default='data/historical',
        help='데이터 디렉토리 (기본: data/historical)',
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data/ml_results',
        help='결과 저장 디렉토리 (기본: data/ml_results)',
    )

    # 기타
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='상세 로그 출력',
    )

    return parser.parse_args()


def main() -> int:
    """메인 함수"""
    args = parse_args()
    setup_logging(args.verbose)

    logger = logging.getLogger(__name__)

    # 모드에 따른 설정
    if args.quick:
        n_random = 10
        n_bayesian = 10
        logger.info("🚀 Quick 모드 (테스트용)")
    elif args.full:
        n_random = 100
        n_bayesian = 200
        logger.info("🚀 Full 모드 (프로덕션)")
    else:
        n_random = args.random_trials
        n_bayesian = args.bayesian_trials
        logger.info(f"🚀 Custom 모드 (random={n_random}, bayesian={n_bayesian})")

    # 설정 생성
    config = OptimizationConfig(
        n_random_trials=n_random,
        n_bayesian_trials=n_bayesian,
        cost_policy=CostPolicy.default(),
    )

    # 데이터 디렉토리 확인
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        logger.error(f"❌ 데이터 디렉토리 없음: {data_dir}")
        return 1

    # 최적화 실행
    try:
        runner = MLOptimizationRunner(
            config=config,
            data_dir=str(data_dir),
            output_dir=args.output_dir,
        )

        result = runner.run_optimization()

        # 결과 출력
        print("\n" + "=" * 60)
        print("📊 최적화 결과 요약")
        print("=" * 60)
        print(f"최적 점수: {result['best_score']:.4f}")
        print(f"Stage 1 최고: {result['stage1_best']:.4f}")
        print(f"Stage 2 최고: {result['stage2_best']:.4f}")
        print(f"소요 시간: {result['duration_seconds']:.1f}초")
        print()

        best_config = result['best_config']
        print("🎯 최적 Config:")
        print(f"  threshold_ratio: {best_config['threshold_ratio']:.3f}")
        print(f"  tier1_filters: {best_config.get('tier1_filters', set())}")
        print()
        print("  filter_weights:")
        for key, value in best_config.get('filter_weights', {}).items():
            print(f"    {key}: {value:.3f}")
        print()
        print("  thresholds:")
        for key, value in best_config.get('thresholds', {}).items():
            print(f"    {key}: {value}")
        print()

        print("📁 결과 저장 위치:")
        print(f"  {args.output_dir}/")
        print("=" * 60)

        return 0

    except Exception as e:
        logger.exception(f"❌ 최적화 실패: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
