@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   GitHub 저장소 설정 및 푸시
echo   Repository: dg_bot
echo ========================================
echo.

REM 현재 디렉토리 확인
echo [1/6] 현재 작업 디렉토리 확인...
cd /d "%~dp0"
echo 작업 디렉토리: %CD%
echo.

REM Git 초기화 확인
if not exist ".git" (
    echo [2/6] Git 저장소 초기화 중...
    git init
    if errorlevel 1 (
        echo [오류] Git 초기화 실패
        pause
        exit /b 1
    )
    echo Git 저장소 초기화 완료
) else (
    echo [2/6] 기존 Git 저장소 발견
)
echo.

REM GitHub 저장소 주소 설정
echo [3/6] GitHub 원격 저장소 설정 중...
git remote remove origin 2>nul
git remote add origin https://github.com/YOUR_USERNAME/dg_bot.git
if errorlevel 1 (
    echo [경고] 원격 저장소 추가 실패 - 이미 존재할 수 있습니다
)
echo.
echo [중요] 위 명령어에서 YOUR_USERNAME을 실제 GitHub 사용자명으로 변경하세요!
echo 예: git remote set-url origin https://github.com/yourusername/dg_bot.git
echo.
pause

REM 모든 파일 스테이징
echo [4/6] 파일 스테이징 중...
git add .
if errorlevel 1 (
    echo [오류] 파일 스테이징 실패
    pause
    exit /b 1
)
echo 파일 스테이징 완료
echo.

REM 커밋
echo [5/6] 커밋 생성 중...
git commit -m "Initial commit: DG Trading Bot

- 비트코인 자동 트레이딩 봇 전체 코드
- 백테스팅 시스템
- AI 분석 모듈
- FastAPI 백엔드
- Docker 환경 설정
- 모니터링 및 알림 시스템"

if errorlevel 1 (
    echo [경고] 커밋 생성 실패 또는 변경사항 없음
)
echo.

REM 브랜치 이름 확인 및 설정
echo [6/6] GitHub에 푸시 준비...
git branch -M main
echo.

echo ========================================
echo   수동 실행 필요
echo ========================================
echo.
echo 다음 명령어를 순서대로 실행하세요:
echo.
echo 1. GitHub에서 수동으로 저장소 생성:
echo    https://github.com/new
echo    Repository name: dg_bot
echo    Description: 비트코인 자동 트레이딩 봇
echo.
echo 2. 원격 저장소 URL 설정:
echo    git remote set-url origin https://github.com/YOUR_USERNAME/dg_bot.git
echo    (YOUR_USERNAME을 실제 사용자명으로 변경)
echo.
echo 3. GitHub에 푸시:
echo    git push -u origin main
echo.
echo 4. 처음 푸시하는 경우 GitHub 인증 필요:
echo    - Personal Access Token 사용 권장
echo    - Settings ^> Developer settings ^> Personal access tokens
echo    - 'repo' 권한 필요
echo.
echo ========================================
pause



