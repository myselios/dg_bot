# 🤖 Bitcoin AI 자동매매 시스템

> AI 기반 비트코인 자동 거래 봇 - TDD로 개발된 안전한 트레이딩 시스템

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/Tests-98.2%25-brightgreen.svg)](./docs/SCHEDULER_GUIDE.md)
[![Scheduler](https://img.shields.io/badge/Scheduler-100%25-success.svg)](./docs/SCHEDULER_GUIDE.md)
[![TDD](https://img.shields.io/badge/TDD-Compliant-brightgreen.svg)](./docs/SCHEDULER_GUIDE.md)

---

## 📋 프로젝트 개요

OpenAI GPT-4를 활용한 AI 자동매매 시스템입니다. 실시간 차트 분석, 기술적 지표, 시장 상황을 종합하여 매수/매도 결정을 내리고 자동으로 거래를 실행합니다.

### ✨ 주요 기능

- 🤖 **AI 기반 거래 결정** - GPT-4를 활용한 지능형 매매 전략
- ⏰ **1시간 주기 자동 실행** - APScheduler 기반 안정적인 스케줄링
- 📊 **백테스팅 지원** - 과거 데이터로 전략 검증
- 🔔 **Telegram 알림** - 실시간 거래 알림
- 📈 **모니터링 대시보드** - Grafana를 통한 시각화
- 🐳 **Docker 지원** - 간편한 배포 및 운영
- 🧪 **TDD 기반 개발** - 283개 테스트 (98.2% 통과)

---

## 📦 GitHub 저장소 설정

이 프로젝트를 GitHub에 업로드하려면:

### 자동 설정 (권장)

```powershell
# PowerShell에서 실행
.\push-to-github.ps1
```

### 수동 설정

```bash
# 1. GitHub에서 저장소 생성 (https://github.com/new)
# 2. 로컬 Git 초기화
git init
git add .
git commit -m "Initial commit: DG Trading Bot"

# 3. 원격 저장소 연결 (YOUR_USERNAME을 실제 사용자명으로 변경)
git remote add origin https://github.com/YOUR_USERNAME/dg_bot.git

# 4. 푸시
git push -u origin main
```

상세 가이드: **[GitHub 설정 가이드](./docs/GITHUB_SETUP_GUIDE.md)**

---

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 저장소 클론
git clone https://github.com/YOUR_USERNAME/dg_bot.git
cd dg_bot

# 가상환경 생성 및 활성화
python -m venv venv

# Windows
.\venv\Scripts\activate.bat

# Linux/Mac
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
pip install -r requirements-api.txt
```

### 2. API 키 설정

```bash
# .env 파일 생성
cp env.example .env

# .env 파일 편집 (필수 항목)
# - UPBIT_ACCESS_KEY
# - UPBIT_SECRET_KEY
# - OPENAI_API_KEY
```

### 3. 백테스팅 (선택)

```bash
# 백테스팅으로 전략 검증
python backtest.py
```

### 4. 자동 거래 실행

#### 방법 1: 로컬 실행

```bash
# Windows
.\start-scheduler.ps1

# Linux/Mac
./start-scheduler.sh
```

#### 방법 2: Docker 실행 (권장)

```bash
# 스케줄러만 실행
docker-compose up -d scheduler

# 전체 스택 실행 (DB, API, 모니터링 포함)
docker-compose -f docker-compose.full-stack.yml up -d

# 로그 확인
docker-compose logs -f scheduler
```

---

## 📚 상세 문서

모든 문서는 [`docs/`](./docs/) 디렉토리에 있습니다.

### 필수 문서

- **[사용자 가이드](./docs/USER_GUIDE.md)** - 전체 사용법 및 설명
- **[스케줄러 가이드](./docs/SCHEDULER_GUIDE.md)** - 자동화 시스템 완벽 가이드
- **[Docker 가이드](./docs/DOCKER_GUIDE.md)** - Docker 실행 및 관리 완벽 가이드
- **[GitHub 설정 가이드](./docs/GITHUB_SETUP_GUIDE.md)** - 저장소 생성 및 코드 업로드 가이드

### 추가 문서

- [시스템 아키텍처](./docs/ARCHITECTURE.md)
- [모니터링 구현 계획](./docs/MONITORING_IMPLEMENTATION_PLAN.md)

---

## 🏗️ 시스템 아키텍처

```
┌──────────────────────────────────────────────┐
│         Scheduler (1시간 주기) ⏰              │
│         (scheduler_main.py)                  │
└──────────────────┬───────────────────────────┘
                   │
         ┌─────────▼─────────┐
         │   Trading Cycle   │
         └─────────┬─────────┘
                   │
      ┌────────────┼────────────┐
      │            │            │
┌─────▼─────┐ ┌───▼────┐ ┌────▼────┐
│  Data     │ │  AI    │ │ Trading │
│ Collector │ │ Service│ │ Service │
└───────────┘ └────────┘ └─────────┘
      │            │            │
      └────────────┼────────────┘
                   │
         ┌─────────▼─────────┐
         │   Upbit Exchange  │
         └───────────────────┘
                   │
      ┌────────────┼────────────┐
      │            │            │
┌─────▼─────┐ ┌───▼────┐ ┌────▼────┐
│ FastAPI   │ │Postgres│ │Grafana  │
│ Backend   │ │   DB   │ │Dashboard│
└───────────┘ └────────┘ └─────────┘
```

---

## 🧪 테스트 현황

```
총 테스트: 283개
통과: 278개 (98.2%)
실패: 5개 (스케줄러 무관)

스케줄러 테스트: 16개 (100%)
코드 커버리지: 48%
```

**테스트 실행:**

```bash
# 전체 테스트
python -m pytest tests/ -v

# 스케줄러 테스트만
python -m pytest tests/backend/app/core/test_scheduler.py -v

# 커버리지 포함
python -m pytest tests/ --cov=src --cov=backend --cov-report=html
```

---

## 📊 주요 기능

### 1. AI 기반 거래 결정

- GPT-4를 활용한 시장 분석
- 기술적 지표 (RSI, MACD, 볼린저 밴드 등)
- 시장 상관관계 분석
- 신뢰도 기반 거래 실행

### 2. 자동 스케줄링

- APScheduler 기반 1시간 주기 실행
- 에러 자동 복구
- 동시 실행 방지
- 안전한 종료 처리

### 3. 백테스팅

- 과거 데이터 기반 전략 검증
- 룰 기반 필터링
- 성능 분석 리포트
- AI 비용 최적화

### 4. 모니터링

- Prometheus 메트릭 수집
- Grafana 대시보드
- Sentry 에러 추적
- Telegram 실시간 알림

---

## 🔒 보안 및 주의사항

⚠️ **실전 거래 시 주의사항:**

1. **API 키 보호**

   - `.env` 파일은 절대 커밋하지 않음
   - `.gitignore`에 포함 확인

2. **소액으로 시작**

   - 처음에는 최소 금액으로 테스트
   - 전략 검증 후 금액 증액

3. **리스크 관리**

   - 손절매 설정 필수
   - 일일 최대 거래 횟수 제한
   - 총 투자 금액 설정

4. **모니터링**
   - 거래 로그 정기적 확인
   - 알림 설정으로 이상 거래 감지
   - 정기적인 성과 분석

---

## 🛠️ 기술 스택

### Core System

- **Python 3.11** - 메인 언어
- **APScheduler** - 자동 거래 스케줄링 (1시간 주기)
- **FastAPI** - REST API 서버
- **SQLAlchemy** - ORM
- **PostgreSQL** - 거래 데이터 저장

### AI & 분석

- **OpenAI GPT-4** - AI 거래 결정
- **TA-Lib** - 기술적 지표
- **pandas** - 데이터 분석
- **numpy** - 수치 계산

### 모니터링 & 관리

- **Prometheus** - 메트릭 수집
- **Grafana** - 시각화 대시보드
- **Sentry** - 에러 추적
- **FastAPI** - REST API (거래 내역 조회, 봇 제어)

### DevOps

- **Docker** - 컨테이너화
- **Docker Compose** - 오케스트레이션
- **pytest** - 테스트 프레임워크

---

## 📈 로드맵

### ✅ 완료

- [x] 백테스팅 시스템
- [x] AI 거래 로직
- [x] 1시간 주기 스케줄러
- [x] Docker 통합
- [x] 단위 테스트 (16개, 100%)
- [x] 통합 테스트 (283개, 98.2%)
- [x] 스케줄러 문서 통합
- [x] Docker 문서 통합 (DOCKER_GUIDE.md)

### 🔜 진행 예정

- [ ] Prometheus 메트릭 수집
- [ ] Grafana 대시보드 구성
- [ ] Sentry 에러 추적 통합
- [ ] 다중 코인 지원
- [ ] 자동 손절/익절 기능
- [ ] 고급 백테스팅 기능

---

## 🤝 기여 가이드

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

**개발 규칙:**

- TDD 원칙 준수
- 테스트 커버리지 70% 이상 유지
- 문서 업데이트 필수
- [`.cursorrules`](./.cursorrules) 참고

---

## 📄 라이센스

이 프로젝트는 MIT 라이센스를 따릅니다. 자세한 내용은 [LICENSE](./LICENSE) 파일을 참고하세요.

---

## 📞 문의

- **이슈**: [GitHub Issues](https://github.com/YOUR_USERNAME/dg_bot/issues)
- **문서**: [docs/](./docs/) 디렉토리 참고
- **개발 규칙**: [.cursorrules](./.cursorrules)

---

## ⭐ 지원

이 프로젝트가 도움이 되었다면 ⭐ Star를 눌러주세요!

---

**최종 업데이트**: 2025-12-28  
**프로젝트 상태**: ✅ 백엔드 API + 스케줄러 중심 아키텍처 완료  
**아키텍처**: 🏗️ Backend API + Scheduler + Monitoring (프론트엔드 제거)  
**다음 단계**: 🔜 Prometheus/Grafana 모니터링 시스템 구현
