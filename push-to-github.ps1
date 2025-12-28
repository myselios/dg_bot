<#
.SYNOPSIS
GitHub 저장소에 코드 푸시

.DESCRIPTION
dg_bot 저장소에 전체 코드를 푸시합니다.
#>

# UTF-8 인코딩 설정 (필수)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
chcp 65001 | Out-Null

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  GitHub 저장소 설정 및 푸시" -ForegroundColor Cyan
Write-Host "  Repository: dg_bot" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 현재 디렉토리로 이동
$ProjectRoot = $PSScriptRoot
if (-not $ProjectRoot) {
    $ProjectRoot = Get-Location
}
Set-Location $ProjectRoot

Write-Host "[1/7] 현재 작업 디렉토리: $ProjectRoot" -ForegroundColor Green
Write-Host ""

# Git 초기화 확인
if (-not (Test-Path ".git")) {
    Write-Host "[2/7] Git 저장소 초기화 중..." -ForegroundColor Yellow
    git init
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[오류] Git 초기화 실패" -ForegroundColor Red
        exit 1
    }
    Write-Host "Git 저장소 초기화 완료" -ForegroundColor Green
} else {
    Write-Host "[2/7] 기존 Git 저장소 발견" -ForegroundColor Green
}
Write-Host ""

# GitHub 사용자명 입력 받기
Write-Host "[3/7] GitHub 사용자 정보 입력" -ForegroundColor Yellow
$githubUsername = Read-Host "GitHub 사용자명을 입력하세요"

if ([string]::IsNullOrWhiteSpace($githubUsername)) {
    Write-Host "[오류] 사용자명이 비어있습니다" -ForegroundColor Red
    exit 1
}

# 원격 저장소 설정
Write-Host ""
Write-Host "[4/7] GitHub 원격 저장소 설정 중..." -ForegroundColor Yellow
git remote remove origin 2>$null
$repoUrl = "https://github.com/$githubUsername/dg_bot.git"
git remote add origin $repoUrl

Write-Host "원격 저장소: $repoUrl" -ForegroundColor Cyan
Write-Host ""

# 모든 파일 스테이징
Write-Host "[5/7] 파일 스테이징 중..." -ForegroundColor Yellow
git add .
if ($LASTEXITCODE -ne 0) {
    Write-Host "[오류] 파일 스테이징 실패" -ForegroundColor Red
    exit 1
}

# 스테이징된 파일 개수 확인
$stagedFiles = git diff --cached --name-only | Measure-Object
Write-Host "스테이징된 파일: $($stagedFiles.Count)개" -ForegroundColor Green
Write-Host ""

# 커밋
Write-Host "[6/7] 커밋 생성 중..." -ForegroundColor Yellow
git commit -m "Initial commit: DG Trading Bot

- 비트코인 자동 트레이딩 봇 전체 코드
- 백테스팅 시스템 (backtesting)
- AI 분석 모듈 (OpenAI GPT-4 통합)
- FastAPI 백엔드 API
- Docker 및 Docker Compose 설정
- PostgreSQL 데이터베이스 스키마
- Prometheus + Grafana 모니터링
- 텔레그램 알림 시스템
- 스케줄러 자동 실행
- 포괄적인 pytest 테스트 스위트
- 상세한 문서 (docs/)
"

if ($LASTEXITCODE -ne 0) {
    Write-Host "[경고] 커밋 생성 실패 또는 변경사항 없음" -ForegroundColor Yellow
}
Write-Host ""

# 브랜치 이름 main으로 변경
git branch -M main
Write-Host "기본 브랜치: main" -ForegroundColor Green
Write-Host ""

# 푸시
Write-Host "[7/7] GitHub에 푸시 중..." -ForegroundColor Yellow
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  중요: GitHub 인증 필요" -ForegroundColor Red
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "GitHub에 처음 푸시하는 경우:" -ForegroundColor Yellow
Write-Host "1. 브라우저에서 https://github.com/new 로 이동" -ForegroundColor White
Write-Host "2. Repository name: dg_bot" -ForegroundColor White
Write-Host "3. Public 또는 Private 선택" -ForegroundColor White
Write-Host "4. 'Create repository' 클릭" -ForegroundColor White
Write-Host "5. Personal Access Token 생성 (Settings > Developer settings > Personal access tokens)" -ForegroundColor White
Write-Host "   - 'repo' 권한 필요" -ForegroundColor White
Write-Host ""
Write-Host "계속하려면 아무 키나 누르세요..." -ForegroundColor Cyan
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
Write-Host ""

git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  푸시 완료!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "저장소 URL: $repoUrl" -ForegroundColor Cyan
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "  푸시 실패" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "가능한 원인:" -ForegroundColor Yellow
    Write-Host "1. GitHub에 저장소가 생성되지 않음" -ForegroundColor White
    Write-Host "2. 인증 실패 (Personal Access Token 필요)" -ForegroundColor White
    Write-Host "3. 네트워크 연결 문제" -ForegroundColor White
    Write-Host ""
    Write-Host "수동으로 푸시하려면:" -ForegroundColor Yellow
    Write-Host "  git push -u origin main" -ForegroundColor White
    Write-Host ""
}



