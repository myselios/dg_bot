@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   스케줄러 컨테이너만 재시작
echo ========================================
echo.

echo [1/2] 스케줄러 컨테이너 중지 및 제거...
docker-compose -f docker-compose.full-stack.yml stop scheduler
docker-compose -f docker-compose.full-stack.yml rm -f scheduler

echo.
echo [2/2] 스케줄러 컨테이너 재시작...
docker-compose -f docker-compose.full-stack.yml up -d scheduler

echo.
echo ========================================
echo   ✅ 스케줄러 재시작 완료
echo ========================================
echo.
echo 로그 확인:
echo   docker-compose -f docker-compose.full-stack.yml logs -f scheduler
echo.

pause



