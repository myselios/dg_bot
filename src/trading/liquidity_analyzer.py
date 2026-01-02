"""
유동성 분석기 - 오더북 기반 슬리피지 계산

실전 거래에서 호가창 데이터를 기반으로 슬리피지를 사전 계산합니다.
대량 매수/매도 시 슬리피지를 예측하여 거래 차단 또는 분할 주문을 결정합니다.
"""
from typing import Dict, List, Optional
from ..utils.logger import Logger
from ..config.settings import SlippageConfig


class LiquidityAnalyzer:
    """유동성 분석기 - 오더북 기반 슬리피지 계산"""

    @staticmethod
    def calculate_slippage(
        orderbook: Dict,
        order_side: str,
        order_krw_amount: float
    ) -> Dict:
        """
        오더북 기반 슬리피지 계산

        Args:
            orderbook: 호가창 데이터 (Upbit API 응답)
                {
                    'orderbook_units': [
                        {
                            'ask_price': float,  # 매도 호가
                            'ask_size': float,   # 매도 수량
                            'bid_price': float,  # 매수 호가
                            'bid_size': float    # 매수 수량
                        },
                        ...
                    ]
                }
            order_side: 'buy' (매수) 또는 'sell' (매도)
            order_krw_amount: 주문 금액 (KRW)

        Returns:
            {
                'expected_slippage_pct': float,  # 예상 슬리피지 비율
                'expected_avg_price': float,     # 예상 평균 체결가
                'liquidity_available': bool,     # 유동성 충분 여부
                'required_levels': int,          # 필요한 호가 단계 수
                'warning': str                   # 경고 메시지
            }
        """
        # 엣지 케이스: 주문 금액이 0
        if order_krw_amount <= 0:
            return {
                'expected_slippage_pct': 0.0,
                'expected_avg_price': 0.0,
                'liquidity_available': True,
                'required_levels': 0,
                'warning': ''
            }

        # 엣지 케이스: 호가창이 비어있음
        orderbook_units = orderbook.get('orderbook_units', [])
        if not orderbook_units:
            return {
                'expected_slippage_pct': float('inf'),
                'expected_avg_price': 0,
                'liquidity_available': False,
                'required_levels': 0,
                'warning': '⚠️ 호가창이 비어있습니다.'
            }

        if order_side == 'buy':
            # 매수 시: 매도 호가창 확인
            return LiquidityAnalyzer._calculate_buy_slippage(orderbook_units, order_krw_amount)
        else:
            # 매도 시: 매수 호가창 확인
            return LiquidityAnalyzer._calculate_sell_slippage(orderbook_units, order_krw_amount)

    @staticmethod
    def _calculate_buy_slippage(asks: List[Dict], order_krw_amount: float) -> Dict:
        """
        매수 슬리피지 계산

        매수 시 매도 호가창(ask)을 소진하면서 체결되므로,
        주문 금액이 클수록 더 높은 가격에 체결됩니다.

        Args:
            asks: 매도 호가창 리스트
            order_krw_amount: 주문 금액 (KRW)

        Returns:
            슬리피지 정보 딕셔너리
        """
        if not asks:
            return {
                'expected_slippage_pct': 0.0,
                'expected_avg_price': 0,
                'liquidity_available': False,
                'required_levels': 0,
                'warning': '오더북 데이터 없음'
            }

        best_ask = asks[0].get('ask_price', 0)
        if best_ask <= 0:
            return {
                'expected_slippage_pct': 0.0,
                'expected_avg_price': 0,
                'liquidity_available': False,
                'required_levels': 0,
                'warning': '유효하지 않은 호가'
            }

        total_krw = 0.0
        total_volume = 0.0
        levels_used = 0

        for level in asks:
            ask_price = level.get('ask_price', 0)
            ask_size = level.get('ask_size', 0)

            if ask_price <= 0 or ask_size <= 0:
                continue

            ask_krw = ask_price * ask_size

            if total_krw + ask_krw >= order_krw_amount:
                # 마지막 단계: 부분 체결
                remaining_krw = order_krw_amount - total_krw
                partial_volume = remaining_krw / ask_price
                total_volume += partial_volume
                total_krw += remaining_krw
                levels_used += 1
                break
            else:
                # 전체 체결
                total_volume += ask_size
                total_krw += ask_krw
                levels_used += 1

        if total_krw < order_krw_amount:
            # 유동성 부족
            return {
                'expected_slippage_pct': float('inf'),
                'expected_avg_price': 0,
                'liquidity_available': False,
                'required_levels': len(asks),
                'warning': f'⚠️ 유동성 부족: 호가창에 {total_krw:,.0f}원만 가능 (주문: {order_krw_amount:,.0f}원)'
            }

        # 평균 체결가 계산
        avg_price = total_krw / total_volume if total_volume > 0 else best_ask

        # 슬리피지 계산
        slippage_pct = ((avg_price - best_ask) / best_ask) * 100 if best_ask > 0 else 0

        # 경고 메시지 (설정값 사용)
        warning = ""
        warning_threshold = SlippageConfig.WARNING_SLIPPAGE_PCT
        if slippage_pct > warning_threshold:
            warning = f"⚠️ 높은 슬리피지 예상: {slippage_pct:.2f}%"
        elif levels_used > 5:
            warning = f"⚠️ 많은 호가 단계 사용: {levels_used}단계"

        return {
            'expected_slippage_pct': slippage_pct,
            'expected_avg_price': avg_price,
            'liquidity_available': True,
            'required_levels': levels_used,
            'warning': warning
        }

    @staticmethod
    def _calculate_sell_slippage(bids: List[Dict], coin_amount: float) -> Dict:
        """
        매도 슬리피지 계산

        매도 시 매수 호가창(bid)을 소진하면서 체결되므로,
        주문 수량이 클수록 더 낮은 가격에 체결됩니다.

        Args:
            bids: 매수 호가창 리스트
            coin_amount: 매도할 코인 수량

        Returns:
            슬리피지 정보 딕셔너리
        """
        if not bids:
            return {
                'expected_slippage_pct': 0.0,
                'expected_avg_price': 0,
                'liquidity_available': False,
                'required_levels': 0,
                'warning': '오더북 데이터 없음'
            }

        best_bid = bids[0].get('bid_price', 0)
        if best_bid <= 0:
            return {
                'expected_slippage_pct': 0.0,
                'expected_avg_price': 0,
                'liquidity_available': False,
                'required_levels': 0,
                'warning': '유효하지 않은 호가'
            }

        total_krw = 0.0
        total_volume = 0.0
        levels_used = 0

        remaining_coin = coin_amount

        for level in bids:
            bid_price = level.get('bid_price', 0)
            bid_size = level.get('bid_size', 0)

            if bid_price <= 0 or bid_size <= 0:
                continue

            if remaining_coin <= 0:
                break

            if remaining_coin >= bid_size:
                # 전체 체결
                total_volume += bid_size
                total_krw += bid_price * bid_size
                remaining_coin -= bid_size
                levels_used += 1
            else:
                # 부분 체결
                total_volume += remaining_coin
                total_krw += bid_price * remaining_coin
                remaining_coin = 0
                levels_used += 1
                break

        if remaining_coin > 0:
            # 유동성 부족
            return {
                'expected_slippage_pct': float('inf'),
                'expected_avg_price': 0,
                'liquidity_available': False,
                'required_levels': len(bids),
                'warning': f'⚠️ 유동성 부족: 호가창에 {total_volume:.8f}개만 가능 (주문: {coin_amount:.8f}개)'
            }

        # 평균 체결가 계산
        avg_price = total_krw / total_volume if total_volume > 0 else best_bid

        # 슬리피지 계산 (매도는 음수)
        slippage_pct = ((avg_price - best_bid) / best_bid) * 100 if best_bid > 0 else 0

        # 경고 메시지 (설정값 사용)
        warning = ""
        warning_threshold = SlippageConfig.WARNING_SLIPPAGE_PCT
        if abs(slippage_pct) > warning_threshold:
            warning = f"⚠️ 높은 슬리피지 예상: {abs(slippage_pct):.2f}%"
        elif levels_used > 5:
            warning = f"⚠️ 많은 호가 단계 사용: {levels_used}단계"

        return {
            'expected_slippage_pct': abs(slippage_pct),  # 절대값 반환
            'expected_avg_price': avg_price,
            'liquidity_available': True,
            'required_levels': levels_used,
            'warning': warning
        }

    @staticmethod
    def check_liquidity_risk(
        orderbook: Dict,
        order_side: str,
        order_krw_amount: float,
        max_slippage_pct: float = None
    ) -> Dict:
        """
        유동성 리스크 체크

        슬리피지가 허용치를 초과하면 거래를 차단하거나
        분할 주문을 권장합니다.

        Args:
            orderbook: 호가창 데이터
            order_side: 'buy' 또는 'sell'
            order_krw_amount: 주문 금액 (KRW)
            max_slippage_pct: 최대 허용 슬리피지 (%)

        Returns:
            {
                'allowed': bool,  # 거래 허용 여부
                'slippage_info': Dict,  # 슬리피지 정보
                'recommendation': str  # 권장 사항
            }
        """
        # 설정값에서 기본 최대 슬리피지 가져오기
        if max_slippage_pct is None:
            max_slippage_pct = SlippageConfig.MAX_SLIPPAGE_PCT

        slippage_info = LiquidityAnalyzer.calculate_slippage(
            orderbook=orderbook,
            order_side=order_side,
            order_krw_amount=order_krw_amount
        )

        if not slippage_info['liquidity_available']:
            return {
                'allowed': False,
                'slippage_info': slippage_info,
                'recommendation': '유동성 부족으로 거래 불가'
            }

        if slippage_info['expected_slippage_pct'] > max_slippage_pct:
            return {
                'allowed': False,
                'slippage_info': slippage_info,
                'recommendation': f'슬리피지 과다 ({slippage_info["expected_slippage_pct"]:.2f}% > {max_slippage_pct:.2f}%), 분할 주문 권장'
            }

        if slippage_info['expected_slippage_pct'] > max_slippage_pct * 0.5:
            return {
                'allowed': True,
                'slippage_info': slippage_info,
                'recommendation': f'주의: 슬리피지 높음 ({slippage_info["expected_slippage_pct"]:.2f}%), 분할 주문 고려'
            }

        return {
            'allowed': True,
            'slippage_info': slippage_info,
            'recommendation': '정상 거래 가능'
        }
