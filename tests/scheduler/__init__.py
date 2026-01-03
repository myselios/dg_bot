"""
Scheduler - 운영 안정성 테스트

이 폴더의 테스트가 실패하면 = 운영 중단

핵심 테스트:
- Configuration: 스케줄러 설정 (타임존, 기본값)
- Trading job: 트레이딩 작업 실행
- Lifecycle: 스케줄러 시작/중지
- Lock mechanism: 작업 간 상호 배제
- Recovery: 장애 복구
"""
