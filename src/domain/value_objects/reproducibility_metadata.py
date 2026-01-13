"""
ReproducibilityMetadata 값 객체

재현성 보장을 위한 메타데이터를 저장하는 불변 값 객체
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Literal, Optional
import hashlib
import subprocess
import sys


VALID_DATA_SOURCES = ("upbit_api", "local_parquet")
VALID_EXCHANGE_ENVS = ("production", "sandbox")


@dataclass(frozen=True)
class ReproducibilityMetadata:
    """
    재현성 메타데이터 값 객체

    백테스트 및 거래 결과의 재현성을 보장하기 위해 필요한 모든 환경 정보를 저장한다.

    Attributes:
        data_hash: 데이터 SHA256 해시 (sha256: 접두사 필수)
        data_version: 데이터 수집 버전
        data_source: 데이터 소스 ("upbit_api" | "local_parquet")
        code_version: Git commit hash
        config_version: FilterConfig 버전
        cost_policy_version: CostPolicy 버전
        fee_rate: 적용된 수수료율
        slippage_model: 적용된 슬리피지 모델
        exchange_env: 거래소 환경 ("production" | "sandbox")
        api_version: Upbit API 버전
        python_version: Python 버전
        numpy_version: NumPy 버전
        pandas_version: Pandas 버전
        timestamp: 생성 시각
    """

    data_hash: str
    data_version: str
    data_source: Literal["upbit_api", "local_parquet"]
    code_version: str
    config_version: str
    cost_policy_version: str
    fee_rate: float
    slippage_model: str
    exchange_env: Literal["production", "sandbox"]
    api_version: str
    python_version: str
    numpy_version: str
    pandas_version: str
    timestamp: datetime

    def __post_init__(self):
        """생성 후 유효성 검증"""
        # 데이터 해시 검증 (sha256: 접두사 필수)
        if not self.data_hash.startswith("sha256:"):
            raise ValueError(
                f"data_hash는 'sha256:' 접두사로 시작해야 합니다: {self.data_hash}"
            )

        # 데이터 소스 검증
        if self.data_source not in VALID_DATA_SOURCES:
            raise ValueError(
                f"data_source는 {VALID_DATA_SOURCES} 중 하나여야 합니다: "
                f"{self.data_source}"
            )

        # 거래소 환경 검증
        if self.exchange_env not in VALID_EXCHANGE_ENVS:
            raise ValueError(
                f"exchange_env는 {VALID_EXCHANGE_ENVS} 중 하나여야 합니다: "
                f"{self.exchange_env}"
            )

    def to_dict(self) -> dict:
        """딕셔너리로 변환 (Parquet 저장용)"""
        result = asdict(self)
        # datetime을 ISO 문자열로 변환
        result["timestamp"] = self.timestamp.isoformat()
        return result

    @classmethod
    def from_current_env(
        cls,
        data_hash: str,
        cost_policy_version: str,
        fee_rate: float,
        slippage_model: str,
        data_version: str = "v1.0.0",
        data_source: Literal["upbit_api", "local_parquet"] = "local_parquet",
        config_version: str = "v1.0.0",
        exchange_env: Literal["production", "sandbox"] = "production",
        api_version: str = "v1",
    ) -> "ReproducibilityMetadata":
        """
        현재 환경에서 메타데이터 자동 생성

        필수 파라미터만 제공하면 나머지는 현재 환경에서 자동 감지한다.
        """
        import numpy
        import pandas

        # Git commit hash 가져오기
        try:
            code_version = (
                subprocess.check_output(
                    ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL
                )
                .decode()
                .strip()
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            code_version = "unknown"

        return cls(
            data_hash=data_hash,
            data_version=data_version,
            data_source=data_source,
            code_version=code_version,
            config_version=config_version,
            cost_policy_version=cost_policy_version,
            fee_rate=fee_rate,
            slippage_model=slippage_model,
            exchange_env=exchange_env,
            api_version=api_version,
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            numpy_version=numpy.__version__,
            pandas_version=pandas.__version__,
            timestamp=datetime.now(),
        )

    @staticmethod
    def calculate_data_hash(df) -> str:
        """
        DataFrame의 SHA256 해시 계산

        Args:
            df: pandas DataFrame (OHLCV 데이터)

        Returns:
            sha256: 접두사가 붙은 해시 문자열
        """
        import pandas as pd

        # DataFrame을 바이트로 변환
        # 재현성을 위해 정렬 후 해시
        if isinstance(df, pd.DataFrame):
            df_sorted = df.sort_index()
            data_bytes = df_sorted.to_csv(index=True).encode("utf-8")
        else:
            data_bytes = str(df).encode("utf-8")

        # SHA256 해시 계산
        hash_value = hashlib.sha256(data_bytes).hexdigest()
        return f"sha256:{hash_value}"
