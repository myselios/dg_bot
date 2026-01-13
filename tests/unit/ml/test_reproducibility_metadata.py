"""
ReproducibilityMetadata 값 객체 테스트

재현성 보장을 위한 메타데이터 테스트
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock


class TestReproducibilityMetadata:
    """ReproducibilityMetadata 값 객체 테스트"""

    def test_metadata_has_required_fields(self):
        """재현성 메타데이터는 필수 필드를 가져야 한다"""
        from src.domain.value_objects.reproducibility_metadata import (
            ReproducibilityMetadata,
        )

        metadata = ReproducibilityMetadata(
            data_hash="sha256:abc123",
            data_version="v1.0.0",
            data_source="upbit_api",
            code_version="abc1234",
            config_version="v1.2.0",
            cost_policy_version="v1.0.0",
            fee_rate=0.0005,
            slippage_model="sqrt",
            exchange_env="production",
            api_version="v1",
            python_version="3.11.0",
            numpy_version="1.24.0",
            pandas_version="2.0.0",
            timestamp=datetime.now(),
        )

        assert metadata.data_hash.startswith("sha256:")
        assert metadata.code_version is not None
        assert metadata.cost_policy_version == "v1.0.0"

    def test_metadata_data_hash_validation(self):
        """데이터 해시는 sha256: 접두사를 가져야 한다"""
        from src.domain.value_objects.reproducibility_metadata import (
            ReproducibilityMetadata,
        )

        # 유효한 해시
        metadata = ReproducibilityMetadata(
            data_hash="sha256:abc123def456",
            data_version="v1.0.0",
            data_source="upbit_api",
            code_version="abc1234",
            config_version="v1.2.0",
            cost_policy_version="v1.0.0",
            fee_rate=0.0005,
            slippage_model="sqrt",
            exchange_env="production",
            api_version="v1",
            python_version="3.11.0",
            numpy_version="1.24.0",
            pandas_version="2.0.0",
            timestamp=datetime.now(),
        )
        assert metadata.data_hash == "sha256:abc123def456"

        # 유효하지 않은 해시 (접두사 없음)
        with pytest.raises(ValueError, match="sha256"):
            ReproducibilityMetadata(
                data_hash="abc123",  # sha256: 접두사 없음
                data_version="v1.0.0",
                data_source="upbit_api",
                code_version="abc1234",
                config_version="v1.2.0",
                cost_policy_version="v1.0.0",
                fee_rate=0.0005,
                slippage_model="sqrt",
                exchange_env="production",
                api_version="v1",
                python_version="3.11.0",
                numpy_version="1.24.0",
                pandas_version="2.0.0",
                timestamp=datetime.now(),
            )

    def test_metadata_data_source_validation(self):
        """데이터 소스는 유효한 값이어야 한다"""
        from src.domain.value_objects.reproducibility_metadata import (
            ReproducibilityMetadata,
        )

        # 유효한 소스
        for source in ["upbit_api", "local_parquet"]:
            metadata = ReproducibilityMetadata(
                data_hash="sha256:abc123",
                data_version="v1.0.0",
                data_source=source,
                code_version="abc1234",
                config_version="v1.2.0",
                cost_policy_version="v1.0.0",
                fee_rate=0.0005,
                slippage_model="sqrt",
                exchange_env="production",
                api_version="v1",
                python_version="3.11.0",
                numpy_version="1.24.0",
                pandas_version="2.0.0",
                timestamp=datetime.now(),
            )
            assert metadata.data_source == source

        # 유효하지 않은 소스
        with pytest.raises(ValueError):
            ReproducibilityMetadata(
                data_hash="sha256:abc123",
                data_version="v1.0.0",
                data_source="invalid_source",
                code_version="abc1234",
                config_version="v1.2.0",
                cost_policy_version="v1.0.0",
                fee_rate=0.0005,
                slippage_model="sqrt",
                exchange_env="production",
                api_version="v1",
                python_version="3.11.0",
                numpy_version="1.24.0",
                pandas_version="2.0.0",
                timestamp=datetime.now(),
            )

    def test_metadata_exchange_env_validation(self):
        """거래소 환경은 production 또는 sandbox여야 한다"""
        from src.domain.value_objects.reproducibility_metadata import (
            ReproducibilityMetadata,
        )

        for env in ["production", "sandbox"]:
            metadata = ReproducibilityMetadata(
                data_hash="sha256:abc123",
                data_version="v1.0.0",
                data_source="upbit_api",
                code_version="abc1234",
                config_version="v1.2.0",
                cost_policy_version="v1.0.0",
                fee_rate=0.0005,
                slippage_model="sqrt",
                exchange_env=env,
                api_version="v1",
                python_version="3.11.0",
                numpy_version="1.24.0",
                pandas_version="2.0.0",
                timestamp=datetime.now(),
            )
            assert metadata.exchange_env == env

    def test_metadata_immutable(self):
        """ReproducibilityMetadata는 불변 객체여야 한다"""
        from src.domain.value_objects.reproducibility_metadata import (
            ReproducibilityMetadata,
        )

        metadata = ReproducibilityMetadata(
            data_hash="sha256:abc123",
            data_version="v1.0.0",
            data_source="upbit_api",
            code_version="abc1234",
            config_version="v1.2.0",
            cost_policy_version="v1.0.0",
            fee_rate=0.0005,
            slippage_model="sqrt",
            exchange_env="production",
            api_version="v1",
            python_version="3.11.0",
            numpy_version="1.24.0",
            pandas_version="2.0.0",
            timestamp=datetime.now(),
        )

        with pytest.raises((AttributeError, TypeError)):
            metadata.data_hash = "sha256:modified"

    def test_metadata_to_dict(self):
        """메타데이터를 딕셔너리로 변환할 수 있어야 한다"""
        from src.domain.value_objects.reproducibility_metadata import (
            ReproducibilityMetadata,
        )

        timestamp = datetime.now()
        metadata = ReproducibilityMetadata(
            data_hash="sha256:abc123",
            data_version="v1.0.0",
            data_source="upbit_api",
            code_version="abc1234",
            config_version="v1.2.0",
            cost_policy_version="v1.0.0",
            fee_rate=0.0005,
            slippage_model="sqrt",
            exchange_env="production",
            api_version="v1",
            python_version="3.11.0",
            numpy_version="1.24.0",
            pandas_version="2.0.0",
            timestamp=timestamp,
        )

        data = metadata.to_dict()

        assert data["data_hash"] == "sha256:abc123"
        assert data["code_version"] == "abc1234"
        assert data["timestamp"] == timestamp.isoformat()


class TestReproducibilityMetadataFactory:
    """ReproducibilityMetadata 팩토리 테스트"""

    def test_create_from_current_environment(self):
        """현재 환경에서 메타데이터 자동 생성"""
        from src.domain.value_objects.reproducibility_metadata import (
            ReproducibilityMetadata,
        )

        # 데이터 해시와 cost_policy_version만 제공하면 나머지는 자동 감지
        metadata = ReproducibilityMetadata.from_current_env(
            data_hash="sha256:abc123",
            cost_policy_version="v1.0.0",
            fee_rate=0.0005,
            slippage_model="sqrt",
        )

        assert metadata.data_hash == "sha256:abc123"
        assert metadata.python_version is not None
        assert metadata.numpy_version is not None
        assert metadata.pandas_version is not None
        assert metadata.timestamp is not None

    def test_calculate_data_hash(self):
        """데이터 해시 계산"""
        from src.domain.value_objects.reproducibility_metadata import (
            ReproducibilityMetadata,
        )
        import pandas as pd
        import numpy as np

        # 테스트용 DataFrame 생성
        df = pd.DataFrame(
            {
                "open": [100.0, 101.0, 102.0],
                "high": [105.0, 106.0, 107.0],
                "low": [95.0, 96.0, 97.0],
                "close": [103.0, 104.0, 105.0],
                "volume": [1000, 1100, 1200],
            }
        )

        hash1 = ReproducibilityMetadata.calculate_data_hash(df)
        hash2 = ReproducibilityMetadata.calculate_data_hash(df)

        # 같은 데이터는 같은 해시
        assert hash1 == hash2
        assert hash1.startswith("sha256:")

        # 다른 데이터는 다른 해시
        df_modified = df.copy()
        df_modified.loc[0, "close"] = 999.0
        hash3 = ReproducibilityMetadata.calculate_data_hash(df_modified)

        assert hash1 != hash3
