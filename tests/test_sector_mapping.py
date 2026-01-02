"""
섹터 매핑 및 섹터별 분산 선택 테스트

TDD Red 단계: 실패하는 테스트 먼저 작성
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from typing import List, Dict
from dataclasses import dataclass, field
from datetime import datetime

# 테스트용 CoinInfo 정의 (의존성 최소화)
@dataclass
class CoinInfo:
    """코인 정보 데이터클래스 (테스트용)"""
    ticker: str
    symbol: str
    korean_name: str
    current_price: float
    volume_24h: float
    acc_trade_price_24h: float
    signed_change_rate: float
    high_price: float
    low_price: float
    volatility_7d: float = None
    avg_volume_7d: float = None
    scan_time: datetime = field(default_factory=datetime.now)

# 테스트 대상
from src.scanner.sector_mapping import (
    CoinSector,
    COIN_SECTOR_MAP,
    get_coin_sector,
    get_coins_by_sector,
    SectorDiversifier
)


class TestCoinSectorMapping:
    """코인 섹터 매핑 테스트"""

    def test_sector_enum_has_required_sectors(self):
        """필수 섹터가 enum에 정의되어 있어야 함"""
        # Given/When: CoinSector enum
        # Then: 필수 섹터들이 존재해야 함
        required_sectors = [
            'INFRASTRUCTURE',
            'SMART_CONTRACT',
            'DEFI',
            'GAMING_ENTERTAINMENT',
            'MEME',
            'AI',
            'LAYER2',
            'UNKNOWN'
        ]
        for sector in required_sectors:
            assert hasattr(CoinSector, sector), f"CoinSector.{sector} should exist"

    def test_btc_is_infrastructure(self):
        """BTC는 인프라 섹터여야 함"""
        # Given
        symbol = "BTC"
        # When
        sector = get_coin_sector(symbol)
        # Then
        assert sector == CoinSector.INFRASTRUCTURE

    def test_eth_is_smart_contract(self):
        """ETH는 스마트 컨트랙트 섹터여야 함"""
        # Given
        symbol = "ETH"
        # When
        sector = get_coin_sector(symbol)
        # Then
        assert sector == CoinSector.SMART_CONTRACT

    def test_sol_is_smart_contract(self):
        """SOL은 스마트 컨트랙트 섹터여야 함"""
        # Given
        symbol = "SOL"
        # When
        sector = get_coin_sector(symbol)
        # Then
        assert sector == CoinSector.SMART_CONTRACT

    def test_doge_is_meme(self):
        """DOGE는 밈코인 섹터여야 함"""
        # Given
        symbol = "DOGE"
        # When
        sector = get_coin_sector(symbol)
        # Then
        assert sector == CoinSector.MEME

    def test_unknown_coin_returns_unknown_sector(self):
        """매핑되지 않은 코인은 UNKNOWN 섹터 반환"""
        # Given
        symbol = "UNKNOWN_COIN_XYZ"
        # When
        sector = get_coin_sector(symbol)
        # Then
        assert sector == CoinSector.UNKNOWN

    def test_get_coins_by_sector(self):
        """특정 섹터의 코인 목록을 가져올 수 있어야 함"""
        # Given
        sector = CoinSector.SMART_CONTRACT
        # When
        coins = get_coins_by_sector(sector)
        # Then
        assert isinstance(coins, list)
        assert "ETH" in coins
        assert "SOL" in coins

    def test_coin_sector_map_covers_major_coins(self):
        """주요 코인들이 매핑되어 있어야 함"""
        # Given: 업비트 주요 코인들
        major_coins = ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE', 'ADA', 'AVAX', 'LINK']
        # When/Then
        for coin in major_coins:
            sector = get_coin_sector(coin)
            assert sector != CoinSector.UNKNOWN, f"{coin} should be mapped to a sector"


class TestSectorDiversifier:
    """섹터 분산기 테스트"""

    @pytest.fixture
    def sample_coins(self) -> List[CoinInfo]:
        """테스트용 코인 목록"""
        return [
            CoinInfo(ticker="KRW-BTC", symbol="BTC", korean_name="비트코인",
                     current_price=100000000, volume_24h=1000, acc_trade_price_24h=50000000000000,
                     signed_change_rate=1.5, high_price=101000000, low_price=99000000),
            CoinInfo(ticker="KRW-ETH", symbol="ETH", korean_name="이더리움",
                     current_price=5000000, volume_24h=5000, acc_trade_price_24h=30000000000000,
                     signed_change_rate=2.0, high_price=5100000, low_price=4900000),
            CoinInfo(ticker="KRW-SOL", symbol="SOL", korean_name="솔라나",
                     current_price=300000, volume_24h=10000, acc_trade_price_24h=20000000000000,
                     signed_change_rate=3.0, high_price=310000, low_price=290000),
            CoinInfo(ticker="KRW-XRP", symbol="XRP", korean_name="리플",
                     current_price=3000, volume_24h=100000, acc_trade_price_24h=25000000000000,
                     signed_change_rate=-1.0, high_price=3100, low_price=2900),
            CoinInfo(ticker="KRW-DOGE", symbol="DOGE", korean_name="도지코인",
                     current_price=500, volume_24h=500000, acc_trade_price_24h=15000000000000,
                     signed_change_rate=5.0, high_price=520, low_price=480),
            CoinInfo(ticker="KRW-SHIB", symbol="SHIB", korean_name="시바이누",
                     current_price=0.02, volume_24h=10000000000, acc_trade_price_24h=12000000000000,
                     signed_change_rate=4.0, high_price=0.021, low_price=0.019),
            CoinInfo(ticker="KRW-AVAX", symbol="AVAX", korean_name="아발란체",
                     current_price=50000, volume_24h=20000, acc_trade_price_24h=18000000000000,
                     signed_change_rate=2.5, high_price=51000, low_price=49000),
        ]

    def test_diversifier_selects_one_per_sector(self, sample_coins):
        """각 섹터에서 하나씩만 선택해야 함"""
        # Given
        diversifier = SectorDiversifier()
        # When
        selected = diversifier.select_diversified(
            coins=sample_coins,
            max_coins=5,
            one_per_sector=True
        )
        # Then
        sectors = [get_coin_sector(c.symbol) for c in selected]
        assert len(sectors) == len(set(sectors)), "각 섹터에서 하나씩만 선택되어야 함"

    def test_diversifier_respects_max_coins(self, sample_coins):
        """max_coins 제한을 준수해야 함"""
        # Given
        diversifier = SectorDiversifier()
        max_coins = 3
        # When
        selected = diversifier.select_diversified(
            coins=sample_coins,
            max_coins=max_coins,
            one_per_sector=True
        )
        # Then
        assert len(selected) <= max_coins

    def test_diversifier_prioritizes_by_volume(self, sample_coins):
        """같은 섹터 내에서는 거래대금이 높은 코인 우선"""
        # Given
        diversifier = SectorDiversifier()
        # When
        selected = diversifier.select_diversified(
            coins=sample_coins,
            max_coins=10,
            one_per_sector=True
        )
        # Then: ETH와 SOL 중 거래대금이 높은 ETH가 선택되어야 함
        symbols = [c.symbol for c in selected]
        # ETH 거래대금 > SOL 거래대금이므로 ETH만 선택
        assert "ETH" in symbols
        assert "SOL" not in symbols  # 같은 섹터이므로 하나만 선택

    def test_diversifier_handles_empty_input(self):
        """빈 입력 처리"""
        # Given
        diversifier = SectorDiversifier()
        # When
        selected = diversifier.select_diversified(
            coins=[],
            max_coins=5,
            one_per_sector=True
        )
        # Then
        assert selected == []

    def test_diversifier_without_sector_constraint(self, sample_coins):
        """one_per_sector=False면 섹터 제한 없이 거래대금 순 선택"""
        # Given
        diversifier = SectorDiversifier()
        # When
        selected = diversifier.select_diversified(
            coins=sample_coins,
            max_coins=5,
            one_per_sector=False
        )
        # Then: 거래대금 상위 5개가 선택되어야 함
        assert len(selected) == 5
        # 거래대금 순 정렬 확인
        volumes = [c.acc_trade_price_24h for c in selected]
        assert volumes == sorted(volumes, reverse=True)

    def test_diversifier_returns_sector_distribution(self, sample_coins):
        """선택 결과와 함께 섹터 분포 정보 제공"""
        # Given
        diversifier = SectorDiversifier()
        # When
        selected = diversifier.select_diversified(
            coins=sample_coins,
            max_coins=5,
            one_per_sector=True
        )
        distribution = diversifier.get_sector_distribution(selected)
        # Then
        assert isinstance(distribution, dict)
        # 선택된 코인 수와 섹터 수가 일치 (one_per_sector=True이므로)
        total_coins = sum(distribution.values())
        assert total_coins == len(selected)

    def test_diversifier_excludes_unknown_sector(self, sample_coins):
        """UNKNOWN 섹터 코인 제외 옵션"""
        # Given
        diversifier = SectorDiversifier()
        # 매핑되지 않은 코인 추가
        unknown_coin = CoinInfo(
            ticker="KRW-UNKNOWNXYZ", symbol="UNKNOWNXYZ", korean_name="알수없음",
            current_price=100, volume_24h=1000000, acc_trade_price_24h=100000000000000,  # 거래대금 최고
            signed_change_rate=10.0, high_price=110, low_price=90
        )
        coins_with_unknown = sample_coins + [unknown_coin]

        # When
        selected = diversifier.select_diversified(
            coins=coins_with_unknown,
            max_coins=5,
            one_per_sector=True,
            exclude_unknown=True
        )
        # Then
        symbols = [c.symbol for c in selected]
        assert "UNKNOWNXYZ" not in symbols


class TestSectorMappingCompleteness:
    """섹터 매핑 완전성 테스트"""

    def test_mapping_includes_upbit_major_coins(self):
        """업비트 주요 거래 코인들이 매핑되어 있어야 함"""
        # 업비트 거래대금 상위 코인들 (2025년 기준)
        upbit_major = [
            # 인프라
            'BTC', 'XRP', 'XLM', 'LINK', 'BCH', 'HBAR',
            # 스마트 컨트랙트
            'ETH', 'SOL', 'ADA', 'AVAX', 'TRX', 'SUI', 'DOT', 'POL', 'ARB',
            # DeFi
            'UNI', 'AAVE',
            # 게임/엔터
            'IMX', 'SAND', 'MANA', 'AXS',
            # 밈코인
            'DOGE', 'SHIB', 'PEPE', 'BONK',
            # AI
            'GRT', 'RENDER', 'FET',
            # Layer2
            'STX', 'OP',
        ]

        unmapped = []
        for coin in upbit_major:
            sector = get_coin_sector(coin)
            if sector == CoinSector.UNKNOWN:
                unmapped.append(coin)

        assert len(unmapped) == 0, f"Unmapped coins: {unmapped}"
