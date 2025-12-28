# GitHub 저장소 설정 가이드

## 📌 개요

이 가이드는 `dg_bot` 프로젝트를 GitHub 저장소에 업로드하는 방법을 설명합니다.

## 🚀 빠른 시작

### 방법 1: PowerShell 스크립트 사용 (권장)

**Windows PowerShell에서 실행:**

```powershell
.\push-to-github.ps1
```

스크립트가 자동으로:
1. Git 저장소 초기화
2. GitHub 사용자명 입력 요청
3. 원격 저장소 설정
4. 모든 파일 커밋
5. GitHub에 푸시

### 방법 2: 배치 파일 사용

**Windows CMD에서 실행:**

```batch
setup-git-and-push.bat
```

### 방법 3: 수동 설정 (고급)

수동으로 Git 명령어를 실행하려면 아래 단계를 따르세요.

## 📋 사전 준비사항

### 1. Git 설치 확인

```bash
git --version
```

Git이 설치되지 않은 경우:
- Windows: https://git-scm.com/download/win
- macOS: `brew install git`
- Linux: `sudo apt-get install git`

### 2. GitHub 계정 준비

GitHub 계정이 없다면 https://github.com/join 에서 생성하세요.

### 3. Personal Access Token 생성

GitHub에서 인증을 위해 Personal Access Token이 필요합니다.

**생성 방법:**

1. GitHub 로그인
2. Settings > Developer settings > Personal access tokens > Tokens (classic)
3. "Generate new token" 클릭
4. Note: `dg_bot access`
5. Expiration: 선택 (권장: 90 days)
6. Scopes: `repo` 체크 ✅
7. "Generate token" 클릭
8. **생성된 토큰을 안전한 곳에 복사** (다시 볼 수 없음!)

## 🔧 수동 설정 단계

### 1. GitHub에서 저장소 생성

1. https://github.com/new 방문
2. Repository name: `dg_bot`
3. Description: `비트코인 자동 트레이딩 봇 - 백테스팅, AI 분석, 자동 매매 시스템`
4. Public/Private 선택
5. **❌ "Initialize this repository with a README" 체크 해제**
6. "Create repository" 클릭

### 2. 로컬 Git 저장소 초기화

프로젝트 루트 디렉토리에서:

```bash
# Git 초기화 (처음 한 번만)
git init

# 기본 브랜치를 main으로 설정
git branch -M main
```

### 3. 원격 저장소 연결

```bash
# YOUR_USERNAME을 실제 GitHub 사용자명으로 변경
git remote add origin https://github.com/YOUR_USERNAME/dg_bot.git

# 원격 저장소 확인
git remote -v
```

### 4. 파일 스테이징 및 커밋

```bash
# 모든 파일 추가 (.gitignore 제외)
git add .

# 스테이징된 파일 확인
git status

# 커밋
git commit -m "Initial commit: DG Trading Bot

- 비트코인 자동 트레이딩 봇 전체 코드
- 백테스팅 시스템
- AI 분석 모듈
- FastAPI 백엔드
- Docker 환경 설정
- 모니터링 및 알림 시스템"
```

### 5. GitHub에 푸시

```bash
# 첫 번째 푸시
git push -u origin main
```

**인증 방법:**

- Username: GitHub 사용자명
- Password: Personal Access Token (위에서 생성한 토큰)

> **주의**: 비밀번호가 아닌 Personal Access Token을 입력해야 합니다!

## 📊 업로드되는 파일 구조

```
dg_bot/
├── README.md                          # 프로젝트 개요
├── requirements.txt                   # Python 의존성
├── requirements-api.txt               # API 서버 의존성
├── docker-compose.yml                 # Docker Compose 설정
├── Dockerfile                         # Docker 이미지 설정
│
├── main.py                            # 메인 실행 파일
├── scheduler_main.py                  # 스케줄러 메인
│
├── src/                               # 소스 코드
│   ├── ai/                            # AI 분석 모듈
│   ├── api/                           # API 클라이언트
│   ├── backtesting/                   # 백테스팅 엔진
│   ├── config/                        # 설정 관리
│   ├── data/                          # 데이터 처리
│   ├── position/                      # 포지션 관리
│   ├── trading/                       # 트레이딩 로직
│   └── utils/                         # 유틸리티
│
├── backend/                           # FastAPI 백엔드
│   ├── app/                           # API 애플리케이션
│   │   ├── api/                       # API 라우터
│   │   ├── core/                      # 핵심 로직
│   │   ├── db/                        # 데이터베이스
│   │   ├── models/                    # ORM 모델
│   │   ├── schemas/                   # Pydantic 스키마
│   │   └── services/                  # 비즈니스 로직
│   └── tests/                         # 백엔드 테스트
│
├── tests/                             # 테스트 스위트
│   ├── integration/                   # 통합 테스트
│   └── backend/                       # 백엔드 테스트
│
├── scripts/                           # 스크립트
│   └── backtesting/                   # 백테스트 스크립트
│
├── docs/                              # 문서
│   ├── reports/                       # 리포트
│   └── diagrams/                      # 다이어그램
│
├── monitoring/                        # 모니터링 설정
│   └── grafana/                       # Grafana 대시보드
│
└── backtest_data/                     # 백테스트 데이터 (선택적)
    ├── daily/
    ├── hourly/
    └── minute/
```

## 🚫 업로드되지 않는 파일

`.gitignore`에 의해 다음 파일들은 제외됩니다:

- `venv/` - Python 가상환경
- `__pycache__/` - Python 캐시
- `.env` - 환경변수 (민감 정보 포함)
- `*.log` - 로그 파일
- `htmlcov/` - 테스트 커버리지 리포트
- `.idea/`, `.vscode/` - IDE 설정
- `*.db`, `*.sqlite` - 데이터베이스 파일

> **중요**: `.env` 파일은 API 키와 같은 민감한 정보를 포함하므로 절대 업로드하지 마세요!
> 대신 `.env.example` 파일을 제공하여 다른 사용자가 참고할 수 있도록 합니다.

## 🔄 업데이트 방법

코드를 수정한 후 GitHub에 업데이트:

```bash
# 변경사항 확인
git status

# 변경된 파일 스테이징
git add .

# 커밋
git commit -m "설명: 변경 내용"

# 푸시
git push origin main
```

## 📝 커밋 메시지 가이드

좋은 커밋 메시지 예시:

```bash
# 기능 추가
git commit -m "feat: 새로운 거래 전략 추가"

# 버그 수정
git commit -m "fix: 슬리피지 계산 오류 수정"

# 문서 업데이트
git commit -m "docs: README 사용법 업데이트"

# 리팩토링
git commit -m "refactor: 백테스팅 엔진 성능 개선"

# 테스트 추가
git commit -m "test: 거래 서비스 단위 테스트 추가"
```

## 🛡️ 보안 주의사항

### ❌ 절대 업로드하면 안 되는 것

1. **API 키 및 비밀 키**
   - Upbit API Key
   - OpenAI API Key
   - Telegram Bot Token

2. **개인 정보**
   - 데이터베이스 비밀번호
   - 실제 거래 내역
   - 수익 정보

3. **환경 설정 파일**
   - `.env` (민감 정보 포함)
   - `config.local.py`

### ✅ 대신 제공해야 할 것

1. **템플릿 파일**
   - `.env.example`
   - `config.example.py`

2. **문서**
   - 설정 방법 가이드
   - API 키 발급 방법

## 🆘 문제 해결

### 문제 1: `git push` 시 인증 실패

**증상:**
```
remote: Support for password authentication was removed...
fatal: Authentication failed
```

**해결:**
- 비밀번호 대신 Personal Access Token 사용
- Token 생성: Settings > Developer settings > Personal access tokens

### 문제 2: 원격 저장소가 이미 존재

**증상:**
```
error: remote origin already exists
```

**해결:**
```bash
git remote remove origin
git remote add origin https://github.com/YOUR_USERNAME/dg_bot.git
```

### 문제 3: 파일이 너무 큼

**증상:**
```
remote: error: File xxx is 100.00 MB; this exceeds GitHub's file size limit of 100.00 MB
```

**해결:**
```bash
# 큰 파일을 .gitignore에 추가
echo "large_file.csv" >> .gitignore
git rm --cached large_file.csv
git commit -m "Remove large file"
```

### 문제 4: 한글 경로 인코딩 오류 (Windows)

**해결:**
```powershell
# PowerShell에서
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001
```

또는 `push-to-github.ps1` 스크립트 사용 (자동 처리됨)

## 📚 추가 리소스

- [Git 공식 문서](https://git-scm.com/doc)
- [GitHub 가이드](https://guides.github.com/)
- [Pro Git 한글판](https://git-scm.com/book/ko/v2)
- [GitHub Personal Access Token 가이드](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)

## 🎯 다음 단계

저장소를 성공적으로 생성한 후:

1. **README.md 작성**
   - 프로젝트 설명
   - 설치 방법
   - 사용 예시

2. **이슈 템플릿 추가**
   - `.github/ISSUE_TEMPLATE/`

3. **CI/CD 설정**
   - GitHub Actions
   - 자동 테스트 실행

4. **라이선스 추가**
   - `LICENSE` 파일

5. **기여 가이드**
   - `CONTRIBUTING.md`

## 📞 문의

문제가 발생하거나 질문이 있으면 GitHub Issues를 통해 문의하세요.

---

**마지막 업데이트:** 2025년 12월 28일



