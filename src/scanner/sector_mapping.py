"""
코인 섹터 매핑 (Coin Sector Mapping)

업비트 상장 코인들의 섹터(산업군) 분류 매핑 테이블입니다.

섹터 분류 기준:
- 업비트 UBCI (UpBit Crypto Index) 대분류/중분류 참조
- 2025년 5월 업비트 '코인 분류' 기능 기준

⚠️ 중요: 새로운 코인이 상장되거나 섹터가 변경되면 이 파일을 업데이트하세요.
마지막 업데이트: 2025-01-02

참조:
- https://www.fnnews.com/news/202505080907372290
- https://simpleinvest.co.kr/코인-섹터-종류-코인-섹터별-대장주/
"""
from enum import Enum
from typing import Dict, List, Optional

from src.scanner.liquidity_scanner import CoinInfo


class CoinSector(Enum):
    """코인 섹터 분류"""
    INFRASTRUCTURE = "infrastructure"          # 인프라 (지급결제, 네트워크, 오라클)
    SMART_CONTRACT = "smart_contract"          # 스마트 컨트랙트 플랫폼
    DEFI = "defi"                              # DeFi (탈중앙화 금융)
    GAMING_ENTERTAINMENT = "gaming_entertainment"  # 게임/엔터테인먼트 (메타버스, NFT)
    MEME = "meme"                              # 밈코인
    AI = "ai"                                  # AI/데이터
    LAYER2 = "layer2"                          # 레이어2 솔루션
    STORAGE = "storage"                        # 분산 저장소 (DePIN)
    PRIVACY = "privacy"                        # 프라이버시 코인
    UNKNOWN = "unknown"                        # 미분류


# 코인 섹터 매핑 테이블
# 키: 코인 심볼 (대문자), 값: CoinSector
COIN_SECTOR_MAP: Dict[str, CoinSector] = {
    # ========================================
    # 인프라 (INFRASTRUCTURE)
    # - 지급결제: BTC, XRP, XLM, BCH, LTC
    # - 네트워크 인프라: HBAR, ATOM, ZRO
    # - 오라클/데이터: LINK, PYTH, API3, BAND
    # ========================================
    "BTC": CoinSector.INFRASTRUCTURE,
    "XRP": CoinSector.INFRASTRUCTURE,
    "XLM": CoinSector.INFRASTRUCTURE,
    "BCH": CoinSector.INFRASTRUCTURE,
    "LTC": CoinSector.INFRASTRUCTURE,
    "HBAR": CoinSector.INFRASTRUCTURE,
    "ATOM": CoinSector.INFRASTRUCTURE,
    "LINK": CoinSector.INFRASTRUCTURE,
    "PYTH": CoinSector.INFRASTRUCTURE,
    "API3": CoinSector.INFRASTRUCTURE,
    "BAND": CoinSector.INFRASTRUCTURE,
    "ZRO": CoinSector.INFRASTRUCTURE,
    "ZETA": CoinSector.INFRASTRUCTURE,
    "AXL": CoinSector.INFRASTRUCTURE,
    "W": CoinSector.INFRASTRUCTURE,
    "ENS": CoinSector.INFRASTRUCTURE,
    "SNT": CoinSector.INFRASTRUCTURE,
    "ANKR": CoinSector.INFRASTRUCTURE,
    "QTUM": CoinSector.INFRASTRUCTURE,
    "EOS": CoinSector.INFRASTRUCTURE,
    "ICX": CoinSector.INFRASTRUCTURE,
    "ONT": CoinSector.INFRASTRUCTURE,
    "IOST": CoinSector.INFRASTRUCTURE,
    "BTT": CoinSector.INFRASTRUCTURE,
    "VET": CoinSector.INFRASTRUCTURE,
    "WAVES": CoinSector.INFRASTRUCTURE,
    "ZIL": CoinSector.INFRASTRUCTURE,
    "TFUEL": CoinSector.INFRASTRUCTURE,
    "KAVA": CoinSector.INFRASTRUCTURE,
    "CRO": CoinSector.INFRASTRUCTURE,
    "XTZ": CoinSector.INFRASTRUCTURE,
    "ALGO": CoinSector.INFRASTRUCTURE,
    "CELO": CoinSector.INFRASTRUCTURE,
    "FLOW": CoinSector.INFRASTRUCTURE,
    "EGLD": CoinSector.INFRASTRUCTURE,
    "AERGO": CoinSector.INFRASTRUCTURE,
    "ONG": CoinSector.INFRASTRUCTURE,
    "META": CoinSector.INFRASTRUCTURE,
    "GLM": CoinSector.INFRASTRUCTURE,
    "POWR": CoinSector.INFRASTRUCTURE,
    "LSK": CoinSector.INFRASTRUCTURE,
    "STRAX": CoinSector.INFRASTRUCTURE,
    "STPT": CoinSector.INFRASTRUCTURE,
    "CVC": CoinSector.INFRASTRUCTURE,
    "STORJ": CoinSector.INFRASTRUCTURE,
    "HIVE": CoinSector.INFRASTRUCTURE,
    "STEEM": CoinSector.INFRASTRUCTURE,
    "SC": CoinSector.INFRASTRUCTURE,
    "XEM": CoinSector.INFRASTRUCTURE,
    "HUNT": CoinSector.INFRASTRUCTURE,
    "MVL": CoinSector.INFRASTRUCTURE,
    "MED": CoinSector.INFRASTRUCTURE,
    "CBK": CoinSector.INFRASTRUCTURE,

    # ========================================
    # 스마트 컨트랙트 플랫폼 (SMART_CONTRACT)
    # - 모놀리식: SOL, ADA, AVAX, TRX, SUI, APT
    # - 모듈러: ETH, DOT, POL, NEAR
    # ========================================
    "ETH": CoinSector.SMART_CONTRACT,
    "SOL": CoinSector.SMART_CONTRACT,
    "ADA": CoinSector.SMART_CONTRACT,
    "AVAX": CoinSector.SMART_CONTRACT,
    "TRX": CoinSector.SMART_CONTRACT,
    "SUI": CoinSector.SMART_CONTRACT,
    "APT": CoinSector.SMART_CONTRACT,
    "DOT": CoinSector.SMART_CONTRACT,
    "POL": CoinSector.SMART_CONTRACT,  # MATIC -> POL 리브랜딩
    "MATIC": CoinSector.SMART_CONTRACT,  # 레거시
    "NEAR": CoinSector.SMART_CONTRACT,
    "FTM": CoinSector.SMART_CONTRACT,
    "TON": CoinSector.SMART_CONTRACT,
    "KLAY": CoinSector.SMART_CONTRACT,
    "ETC": CoinSector.SMART_CONTRACT,
    "XEC": CoinSector.SMART_CONTRACT,
    "BORA": CoinSector.SMART_CONTRACT,
    "WEMIX": CoinSector.SMART_CONTRACT,
    "SEI": CoinSector.SMART_CONTRACT,
    "ICP": CoinSector.SMART_CONTRACT,
    "INJ": CoinSector.SMART_CONTRACT,
    "MINA": CoinSector.SMART_CONTRACT,
    "ROSE": CoinSector.SMART_CONTRACT,
    "CFX": CoinSector.SMART_CONTRACT,
    "STG": CoinSector.SMART_CONTRACT,
    "NEO": CoinSector.SMART_CONTRACT,

    # ========================================
    # DeFi (DEFI)
    # - DEX: UNI, RAY, JUP, 1INCH, ZRX, CAKE, SUSHI
    # - 렌딩/예치: AAVE, COMP, SNX, MKR
    # - 파생상품: GMX, PERP
    # ========================================
    "UNI": CoinSector.DEFI,
    "AAVE": CoinSector.DEFI,
    "COMP": CoinSector.DEFI,
    "SNX": CoinSector.DEFI,
    "MKR": CoinSector.DEFI,
    "CRV": CoinSector.DEFI,
    "LDO": CoinSector.DEFI,
    "RPL": CoinSector.DEFI,
    "PENDLE": CoinSector.DEFI,
    "ONDO": CoinSector.DEFI,
    "GMX": CoinSector.DEFI,
    "1INCH": CoinSector.DEFI,
    "ZRX": CoinSector.DEFI,
    "CAKE": CoinSector.DEFI,
    "SUSHI": CoinSector.DEFI,
    "JUP": CoinSector.DEFI,
    "RAY": CoinSector.DEFI,
    "BAL": CoinSector.DEFI,
    "DYDX": CoinSector.DEFI,
    "KNC": CoinSector.DEFI,
    "BAKE": CoinSector.DEFI,
    "SRM": CoinSector.DEFI,
    "ORC": CoinSector.DEFI,
    "SSX": CoinSector.DEFI,

    # ========================================
    # 게임/엔터테인먼트 (GAMING_ENTERTAINMENT)
    # - 메타버스: SAND, MANA, APE
    # - 게임: AXS, IMX, GALA, BEAM, RON
    # - NFT: BLUR
    # - 팬토큰: CHZ
    # ========================================
    "IMX": CoinSector.GAMING_ENTERTAINMENT,
    "SAND": CoinSector.GAMING_ENTERTAINMENT,
    "MANA": CoinSector.GAMING_ENTERTAINMENT,
    "AXS": CoinSector.GAMING_ENTERTAINMENT,
    "APE": CoinSector.GAMING_ENTERTAINMENT,
    "GALA": CoinSector.GAMING_ENTERTAINMENT,
    "BEAM": CoinSector.GAMING_ENTERTAINMENT,
    "RON": CoinSector.GAMING_ENTERTAINMENT,
    "ENJ": CoinSector.GAMING_ENTERTAINMENT,
    "CHZ": CoinSector.GAMING_ENTERTAINMENT,
    "BLUR": CoinSector.GAMING_ENTERTAINMENT,
    "MAGIC": CoinSector.GAMING_ENTERTAINMENT,
    "ILV": CoinSector.GAMING_ENTERTAINMENT,
    "GODS": CoinSector.GAMING_ENTERTAINMENT,
    "YGG": CoinSector.GAMING_ENTERTAINMENT,
    "PLA": CoinSector.GAMING_ENTERTAINMENT,
    "WAXP": CoinSector.GAMING_ENTERTAINMENT,
    "MBL": CoinSector.GAMING_ENTERTAINMENT,
    "STMX": CoinSector.GAMING_ENTERTAINMENT,
    "MLK": CoinSector.GAMING_ENTERTAINMENT,
    "XPR": CoinSector.GAMING_ENTERTAINMENT,
    "SXP": CoinSector.GAMING_ENTERTAINMENT,
    "GAS": CoinSector.GAMING_ENTERTAINMENT,
    "GHST": CoinSector.GAMING_ENTERTAINMENT,
    "T": CoinSector.GAMING_ENTERTAINMENT,

    # ========================================
    # 밈코인 (MEME)
    # ========================================
    "DOGE": CoinSector.MEME,
    "SHIB": CoinSector.MEME,
    "PEPE": CoinSector.MEME,
    "BONK": CoinSector.MEME,
    "WIF": CoinSector.MEME,
    "FLOKI": CoinSector.MEME,
    "MOG": CoinSector.MEME,
    "BRETT": CoinSector.MEME,
    "NEIRO": CoinSector.MEME,
    "POPCAT": CoinSector.MEME,
    "PEOPLE": CoinSector.MEME,
    "BOME": CoinSector.MEME,
    "TRUMP": CoinSector.MEME,
    "MOODENG": CoinSector.MEME,

    # ========================================
    # AI/데이터 (AI)
    # - AI 인프라: RENDER, FET, TAO
    # - 데이터: GRT, OCEAN, NMR
    # ========================================
    "GRT": CoinSector.AI,
    "RENDER": CoinSector.AI,
    "FET": CoinSector.AI,
    "TAO": CoinSector.AI,
    "OCEAN": CoinSector.AI,
    "NMR": CoinSector.AI,
    "AGIX": CoinSector.AI,
    "ARKM": CoinSector.AI,
    "WLD": CoinSector.AI,
    "AI": CoinSector.AI,
    "RNDR": CoinSector.AI,  # RENDER 별칭

    # ========================================
    # 레이어2 (LAYER2)
    # - 이더리움 L2: ARB, OP, STRK, ZK
    # - 비트코인 L2: STX
    # ========================================
    "ARB": CoinSector.LAYER2,
    "OP": CoinSector.LAYER2,
    "STX": CoinSector.LAYER2,
    "STRK": CoinSector.LAYER2,
    "ZK": CoinSector.LAYER2,
    "MNT": CoinSector.LAYER2,
    "METIS": CoinSector.LAYER2,
    "LRC": CoinSector.LAYER2,
    "BOBA": CoinSector.LAYER2,
    "COTI": CoinSector.LAYER2,
    "SKL": CoinSector.LAYER2,

    # ========================================
    # 분산 저장소 / DePIN (STORAGE)
    # ========================================
    "FIL": CoinSector.STORAGE,
    "AR": CoinSector.STORAGE,
    "THETA": CoinSector.STORAGE,
    "HNT": CoinSector.STORAGE,
    "IOTX": CoinSector.STORAGE,
    "IOTA": CoinSector.STORAGE,
    "JASMY": CoinSector.STORAGE,

    # ========================================
    # 프라이버시 (PRIVACY)
    # ========================================
    "XMR": CoinSector.PRIVACY,
    "ZEC": CoinSector.PRIVACY,
    "DASH": CoinSector.PRIVACY,
    "SCRT": CoinSector.PRIVACY,
}


def get_coin_sector(symbol: str) -> CoinSector:
    """
    코인 심볼로 섹터 조회

    Args:
        symbol: 코인 심볼 (예: BTC, ETH)

    Returns:
        CoinSector: 해당 코인의 섹터 (매핑 없으면 UNKNOWN)
    """
    return COIN_SECTOR_MAP.get(symbol.upper(), CoinSector.UNKNOWN)


def get_coins_by_sector(sector: CoinSector) -> List[str]:
    """
    특정 섹터에 속한 코인 목록 조회

    Args:
        sector: CoinSector enum 값

    Returns:
        List[str]: 해당 섹터의 코인 심볼 리스트
    """
    return [symbol for symbol, s in COIN_SECTOR_MAP.items() if s == sector]


def get_sector_korean_name(sector: CoinSector) -> str:
    """섹터 한글명 반환"""
    names = {
        CoinSector.INFRASTRUCTURE: "인프라",
        CoinSector.SMART_CONTRACT: "스마트 컨트랙트",
        CoinSector.DEFI: "DeFi",
        CoinSector.GAMING_ENTERTAINMENT: "게임/엔터",
        CoinSector.MEME: "밈코인",
        CoinSector.AI: "AI/데이터",
        CoinSector.LAYER2: "레이어2",
        CoinSector.STORAGE: "스토리지",
        CoinSector.PRIVACY: "프라이버시",
        CoinSector.UNKNOWN: "미분류",
    }
    return names.get(sector, "미분류")


class SectorDiversifier:
    """
    섹터 분산 선택기

    유동성 상위 코인 중에서 섹터별로 분산하여 선택합니다.
    같은 섹터의 코인은 하나만 선택하여 포트폴리오 다양성을 확보합니다.

    사용 예시:
        diversifier = SectorDiversifier()
        coins = await liquidity_scanner.scan_top_coins(top_n=20)
        diversified = diversifier.select_diversified(coins, max_coins=5, one_per_sector=True)
    """

    def __init__(
        self,
        sector_priority: Optional[List[CoinSector]] = None
    ):
        """
        Args:
            sector_priority: 섹터 우선순위 (None이면 기본 우선순위 사용)
        """
        self.sector_priority = sector_priority or [
            CoinSector.SMART_CONTRACT,  # 스마트 컨트랙트 플랫폼 우선
            CoinSector.INFRASTRUCTURE,
            CoinSector.DEFI,
            CoinSector.AI,
            CoinSector.LAYER2,
            CoinSector.GAMING_ENTERTAINMENT,
            CoinSector.MEME,
            CoinSector.STORAGE,
            CoinSector.PRIVACY,
            CoinSector.UNKNOWN,
        ]

    def select_diversified(
        self,
        coins: List[CoinInfo],
        max_coins: int = 5,
        one_per_sector: bool = True,
        exclude_unknown: bool = False
    ) -> List[CoinInfo]:
        """
        섹터 분산 선택

        Args:
            coins: 후보 코인 목록 (거래대금 순 정렬 권장)
            max_coins: 최대 선택 코인 수
            one_per_sector: True면 섹터당 1개만 선택
            exclude_unknown: True면 UNKNOWN 섹터 코인 제외

        Returns:
            List[CoinInfo]: 선택된 코인 목록
        """
        if not coins:
            return []

        if not one_per_sector:
            # 섹터 제한 없이 거래대금 순
            sorted_coins = sorted(
                coins,
                key=lambda c: c.acc_trade_price_24h,
                reverse=True
            )
            if exclude_unknown:
                sorted_coins = [
                    c for c in sorted_coins
                    if get_coin_sector(c.symbol) != CoinSector.UNKNOWN
                ]
            return sorted_coins[:max_coins]

        # 섹터별 분산 선택
        selected: List[CoinInfo] = []
        selected_sectors: set = set()

        # 거래대금 순 정렬
        sorted_coins = sorted(
            coins,
            key=lambda c: c.acc_trade_price_24h,
            reverse=True
        )

        for coin in sorted_coins:
            if len(selected) >= max_coins:
                break

            sector = get_coin_sector(coin.symbol)

            # UNKNOWN 섹터 제외 옵션
            if exclude_unknown and sector == CoinSector.UNKNOWN:
                continue

            # 이미 선택된 섹터면 스킵
            if sector in selected_sectors:
                continue

            selected.append(coin)
            selected_sectors.add(sector)

        return selected

    def get_sector_distribution(
        self,
        coins: List[CoinInfo]
    ) -> Dict[CoinSector, int]:
        """
        코인 목록의 섹터 분포 조회

        Args:
            coins: 코인 목록

        Returns:
            Dict[CoinSector, int]: 섹터별 코인 수
        """
        distribution: Dict[CoinSector, int] = {}

        for coin in coins:
            sector = get_coin_sector(coin.symbol)
            distribution[sector] = distribution.get(sector, 0) + 1

        return distribution

    def print_sector_distribution(self, coins: List[CoinInfo]) -> None:
        """섹터 분포 출력"""
        distribution = self.get_sector_distribution(coins)

        print("\n📊 섹터 분포:")
        print(f"{'섹터':<15} {'코인 수':>8} {'코인 목록':<30}")
        print("-" * 55)

        for sector in self.sector_priority:
            count = distribution.get(sector, 0)
            if count > 0:
                sector_coins = [
                    c.symbol for c in coins
                    if get_coin_sector(c.symbol) == sector
                ]
                coins_str = ", ".join(sector_coins[:5])
                if len(sector_coins) > 5:
                    coins_str += f" (+{len(sector_coins) - 5})"
                print(f"{get_sector_korean_name(sector):<15} {count:>8} {coins_str:<30}")


# 모듈 테스트용
if __name__ == "__main__":
    # 섹터별 코인 수 출력
    print("=== 섹터별 코인 매핑 현황 ===")
    for sector in CoinSector:
        coins = get_coins_by_sector(sector)
        print(f"{get_sector_korean_name(sector):12}: {len(coins):3}개 - {', '.join(coins[:5])}{'...' if len(coins) > 5 else ''}")

    # 특정 코인 섹터 조회 테스트
    print("\n=== 코인 섹터 조회 테스트 ===")
    test_coins = ['BTC', 'ETH', 'SOL', 'DOGE', 'GRT', 'ARB', 'UNKNOWN_COIN']
    for coin in test_coins:
        sector = get_coin_sector(coin)
        print(f"{coin}: {get_sector_korean_name(sector)} ({sector.value})")
