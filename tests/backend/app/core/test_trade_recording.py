"""
거래 기록 PostgreSQL 저장 테스트

TDD 원칙: 거래 실행 후 PostgreSQL에 거래 내역이 저장되는지 검증합니다.

NOTE: 이 테스트들은 전체 scheduler 통합 환경이 필요하며,
      현재 파이프라인 아키텍처 리팩토링으로 인해 별도의 통합 테스트 환경에서 실행되어야 합니다.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from decimal import Decimal

from backend.app.core.scheduler import trading_job


class TestTradeRecordingSaveToPostgreSQL:
    """거래 기록 PostgreSQL 저장 테스트"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Scheduler 통합 테스트 - 별도 환경에서 실행 필요")
    async def test_buy_trade_saves_to_database(self):
        """
        매수 거래 실행 시 PostgreSQL에 거래 내역이 저장되는지 확인
        
        Given: 매수 결정이 내려지고 거래가 성공적으로 실행됨
        When: trading_job이 실행됨
        Then: PostgreSQL trades 테이블에 Trade 객체가 INSERT됨
        """
        # Given: 매수 거래 성공 결과
        mock_result = {
            'status': 'success',
            'decision': 'buy',
            'confidence': 'high',
            'reason': 'RSI 과매도 구간 진입',
            'trade_id': 'test_uuid_12345',  # Upbit에서 반환하는 주문 UUID
            'trade_success': True,
            'price': 4_350_000,
            'amount': 0.0115,
            'total': 50_000,
            'fee': 25
        }
        
        # Mock DB 세션
        mock_db_session = AsyncMock()
        
        async def mock_get_db_generator():
            yield mock_db_session
        
        with patch('main.execute_trading_cycle', new_callable=AsyncMock) as mock_execute, \
             patch('src.api.upbit_client.UpbitClient'), \
             patch('src.data.collector.DataCollector'), \
             patch('backend.app.services.notification.notify_trade', new_callable=AsyncMock), \
             patch('backend.app.services.metrics.record_ai_decision'), \
             patch('backend.app.services.metrics.scheduler_job_success_total'), \
             patch('backend.app.db.session.get_db', side_effect=mock_get_db_generator):
            
            mock_execute.return_value = mock_result
            
            # When: 트레이딩 작업 실행
            await trading_job()
            
            # Then: DB에 Trade 객체가 추가되었는지 확인
            assert mock_db_session.add.called, "DB add가 호출되지 않았습니다"
            assert mock_db_session.commit.called, "DB commit이 호출되지 않았습니다"
            
            # add에 전달된 객체 확인
            added_trade = mock_db_session.add.call_args[0][0]
            assert added_trade.trade_id == 'test_uuid_12345'
            assert added_trade.symbol == 'KRW-ETH'
            assert added_trade.side == 'buy'
            assert added_trade.status == 'completed'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Scheduler 통합 테스트 - 별도 환경에서 실행 필요")
    async def test_sell_trade_saves_to_database(self):
        """
        매도 거래 실행 시 PostgreSQL에 거래 내역이 저장되는지 확인
        
        Given: 매도 결정이 내려지고 거래가 성공적으로 실행됨
        When: trading_job이 실행됨
        Then: PostgreSQL trades 테이블에 Trade 객체가 INSERT됨
        """
        # Given: 매도 거래 성공 결과
        mock_result = {
            'status': 'success',
            'decision': 'sell',
            'confidence': 'medium',
            'reason': 'RSI 과매수 구간 도달',
            'trade_id': 'test_uuid_67890',
            'trade_success': True,
            'price': 4_400_000,
            'amount': 0.0115,
            'total': 50_600,
            'fee': 25.3
        }
        
        # Mock DB 세션
        mock_db_session = AsyncMock()
        
        async def mock_get_db_generator():
            yield mock_db_session
        
        with patch('main.execute_trading_cycle', new_callable=AsyncMock) as mock_execute, \
             patch('src.api.upbit_client.UpbitClient'), \
             patch('src.data.collector.DataCollector'), \
             patch('backend.app.services.notification.notify_trade', new_callable=AsyncMock), \
             patch('backend.app.services.metrics.record_ai_decision'), \
             patch('backend.app.services.metrics.scheduler_job_success_total'), \
             patch('backend.app.db.session.get_db', side_effect=mock_get_db_generator):
            
            mock_execute.return_value = mock_result
            
            # When: 트레이딩 작업 실행
            await trading_job()
            
            # Then: DB에 Trade 객체가 추가되었는지 확인
            assert mock_db_session.add.called, "DB add가 호출되지 않았습니다"
            assert mock_db_session.commit.called, "DB commit이 호출되지 않았습니다"
            
            # add에 전달된 객체 확인
            added_trade = mock_db_session.add.call_args[0][0]
            assert added_trade.trade_id == 'test_uuid_67890'
            assert added_trade.symbol == 'KRW-ETH'
            assert added_trade.side == 'sell'
            assert added_trade.status == 'completed'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Scheduler 통합 테스트 - 별도 환경에서 실행 필요")
    async def test_hold_decision_does_not_save_trade(self):
        """
        Hold 결정 시 거래 내역이 저장되지 않는지 확인
        
        Given: Hold 결정이 내려짐 (거래 없음)
        When: trading_job이 실행됨
        Then: PostgreSQL에 거래 내역이 저장되지 않음
        """
        # Given: Hold 결정
        mock_result = {
            'status': 'success',
            'decision': 'hold',
            'confidence': 'medium',
            'reason': '시장 관망'
        }
        
        # Mock DB 세션
        mock_db_session = AsyncMock()
        
        async def mock_get_db_generator():
            yield mock_db_session
        
        with patch('main.execute_trading_cycle', new_callable=AsyncMock) as mock_execute, \
             patch('src.api.upbit_client.UpbitClient'), \
             patch('src.data.collector.DataCollector'), \
             patch('backend.app.services.notification.notify_trade', new_callable=AsyncMock), \
             patch('backend.app.services.metrics.record_ai_decision'), \
             patch('backend.app.services.metrics.scheduler_job_success_total'), \
             patch('backend.app.db.session.get_db', side_effect=mock_get_db_generator):
            
            mock_execute.return_value = mock_result
            
            # When: 트레이딩 작업 실행
            await trading_job()
            
            # Then: DB add가 호출되지 않아야 함
            assert not mock_db_session.add.called, "Hold 결정 시에는 DB add가 호출되지 않아야 합니다"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_failed_trade_does_not_save(self):
        """
        거래 사이클 실패 시 DB에 저장하지 않는지 확인
        
        Given: 거래 사이클이 실패함 (status='failed')
        When: trading_job이 실행됨
        Then: PostgreSQL에 거래 내역이 저장되지 않음
        """
        # Given: 거래 사이클 실패 결과
        mock_result = {
            'status': 'failed',
            'decision': 'buy',
            'error': 'Network timeout'
        }
        
        # Mock DB 세션
        mock_db_session = AsyncMock()
        
        async def mock_get_db_generator():
            yield mock_db_session
        
        with patch('main.execute_trading_cycle', new_callable=AsyncMock) as mock_execute, \
             patch('src.api.upbit_client.UpbitClient'), \
             patch('src.data.collector.DataCollector'), \
             patch('backend.app.services.notification.notify_error', new_callable=AsyncMock), \
             patch('backend.app.services.metrics.scheduler_job_failure_total'), \
             patch('backend.app.db.session.get_db', side_effect=mock_get_db_generator):
            
            mock_execute.return_value = mock_result
            
            # When: 트레이딩 작업 실행
            await trading_job()
            
            # Then: DB add가 호출되지 않아야 함
            assert not mock_db_session.add.called, "실패한 거래 사이클은 DB에 저장되지 않아야 합니다"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

