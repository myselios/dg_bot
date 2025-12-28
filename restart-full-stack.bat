@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================================
echo   🚀 Full Stack 재시작 스크립트
echo ============================================================
echo.
echo 실행 순서:
echo   1. 모든 컨테이너 중지 및 제거
echo   2. 이미지 재빌드
echo   3. 컨테이너 시작
echo ============================================================
echo.

echo [1/3] 기존 컨테이너 중지 및 제거 중...
docker-compose -f docker-compose.full-stack.yml down
if %ERRORLEVEL% NEQ 0 (
    echo ❌ 컨테이너 중지 실패
    echo.
    pause
    exit /b 1
)
echo ✅ 중지 완료
echo.

echo [2/3] 이미지 재빌드 중... (시간이 걸릴 수 있습니다)
docker-compose -f docker-compose.full-stack.yml build
if %ERRORLEVEL% NEQ 0 (
    echo ❌ 이미지 빌드 실패
    echo.
    pause
    exit /b 1
)
echo ✅ 빌드 완료
echo.

echo [3/3] 컨테이너 시작 중...
docker-compose -f docker-compose.full-stack.yml up -d
if %ERRORLEVEL% NEQ 0 (
    echo ❌ 컨테이너 시작 실패
    echo.
    pause
    exit /b 1
)
echo ✅ 시작 완료
echo.

echo ============================================================
echo   🎉 Full Stack 재시작 완료!
echo ============================================================
echo.
echo 실행 중인 컨테이너 확인:
docker-compose -f docker-compose.full-stack.yml ps
echo.
echo ============================================================
echo   📋 유용한 명령어
echo ============================================================
echo   전체 로그 확인:
echo   docker-compose -f docker-compose.full-stack.yml logs -f
echo.
echo   스케줄러 로그만 확인:
echo   docker-compose -f docker-compose.full-stack.yml logs -f trading_bot_scheduler
echo.
echo   백엔드 API 로그만 확인:
echo   docker-compose -f docker-compose.full-stack.yml logs -f trading_bot_backend
echo.
echo   Grafana 대시보드 접속:
echo   http://localhost:3000 (admin/admin)
echo.
echo   Prometheus 메트릭 확인:
echo   http://localhost:9090
echo.
echo   모든 컨테이너 중지:
echo   docker-compose -f docker-compose.full-stack.yml down
echo ============================================================
echo.

pause

