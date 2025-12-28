# Mermaid 다이어그램을 이미지로 변환하는 방법

## 📋 개요

`TRADING_SEQUENCE_FLOW.md` 문서의 Mermaid 다이어그램을 PNG/SVG 이미지로 변환하는 가이드입니다.

---

## 🌐 방법 1: Mermaid Live Editor (추천 - 가장 간단)

### 장점

- ✅ 설치 불필요
- ✅ 즉시 사용 가능
- ✅ 100% 성공 보장

### 단계별 가이드

1. **Mermaid Live Editor 열기**

   ```
   https://mermaid.live/
   ```

2. **다이어그램 파일 열기**

   - `docs/diagrams/` 폴더의 `.mmd` 파일 중 하나를 선택
   - 파일 내용 전체를 복사 (Ctrl+A → Ctrl+C)

3. **Mermaid Live Editor에 붙여넣기**

   - 왼쪽 편집 영역에 붙여넣기 (Ctrl+V)
   - 오른쪽에서 실시간 미리보기 확인

4. **이미지 다운로드**

   - 상단 메뉴: **Actions** 클릭
   - **PNG** 또는 **SVG** 선택
   - 다운로드 완료!

5. **저장 위치**
   ```
   docs/images/01-overall-system-flow.png
   docs/images/02-scheduler-module-flow.png
   docs/images/03-trading-execution-flow.png
   docs/images/04-database-save-flow.png
   docs/images/05-monitoring-notification-flow.png
   docs/images/06-error-handling-flow.png
   ```

---

## 📂 다이어그램 파일 목록

총 6개의 다이어그램 파일이 준비되어 있습니다:

### 1. 전체 시스템 흐름도

- **파일**: `docs/diagrams/01-overall-system-flow.mmd`
- **설명**: 전체 거래 사이클의 엔드-투-엔드 흐름
- **참여자**: Scheduler, BackendScheduler, Main, TradingService, Upbit, DB, API, Metrics, Telegram

### 2. 스케줄러 모듈 흐름

- **파일**: `docs/diagrams/02-scheduler-module-flow.mmd`
- **설명**: 스케줄러가 주기적으로 거래 작업을 실행하는 과정
- **참여자**: User, Scheduler, APScheduler, BackendScheduler, Logger

### 3. 거래 실행 모듈 흐름

- **파일**: `docs/diagrams/03-trading-execution-flow.mmd`
- **설명**: 실제 거래가 실행되는 상세 흐름 (4단계)
- **참여자**: BackendScheduler, Main, PositionService, DataCollector, AIService, BacktestRunner, TradingService, Upbit

### 4. 데이터베이스 저장 흐름

- **파일**: `docs/diagrams/04-database-save-flow.mmd`
- **설명**: 거래 결과가 데이터베이스에 저장되는 과정
- **참여자**: BackendScheduler, API, TradeService, DB, Schema

### 5. 모니터링 및 알림 흐름

- **파일**: `docs/diagrams/05-monitoring-notification-flow.mmd`
- **설명**: 거래 완료 후 메트릭 기록과 알림 전송
- **참여자**: BackendScheduler, MetricsService, Prometheus, NotificationService, Telegram, Grafana

### 6. 에러 처리 흐름

- **파일**: `docs/diagrams/06-error-handling-flow.mmd`
- **설명**: 시스템의 에러 처리 및 복구 메커니즘
- **참여자**: Scheduler, ErrorHandler, Logger, Metrics, Telegram, Retry

---

## 🖼️ 추천 이미지 설정

### PNG 다운로드 시 권장 설정

- **포맷**: PNG (투명 배경 가능)
- **너비**: 1920px (고해상도)
- **용도**: 문서, 프레젠테이션, 웹

### SVG 다운로드 시

- **포맷**: SVG (벡터 이미지)
- **장점**: 확대/축소 시 화질 손실 없음
- **용도**: 인쇄, 대형 디스플레이

---

## 🚀 빠른 시작 (5분 완료)

```bash
# 1. 브라우저에서 Mermaid Live Editor 열기
start https://mermaid.live/

# 2. 파일 탐색기에서 다이어그램 폴더 열기
explorer docs\diagrams

# 3. 각 .mmd 파일을 하나씩:
#    - 파일 열기 → 전체 복사
#    - Mermaid Live Editor에 붙여넣기
#    - PNG 다운로드
#    - docs/images/ 폴더에 저장

# 4. 완료! 🎉
```

---

## 💡 팁

### 1. 배경 투명하게 만들기

Mermaid Live Editor에서:

- 좌측 하단: **Configuration** 클릭
- `theme` 항목 찾기
- `"default"` → `"neutral"` 변경 (깔끔한 디자인)

### 2. 글자 크기 조정

Configuration에서:

```json
{
  "theme": "default",
  "themeVariables": {
    "fontSize": "16px"
  }
}
```

### 3. 다이어그램 너비 조정

```json
{
  "theme": "default",
  "width": 1920
}
```

---

## 🔧 방법 2: Mermaid CLI (고급 사용자용)

Node.js가 설치되어 있다면 CLI를 사용할 수 있습니다.

### 설치

```bash
npm install -g @mermaid-js/mermaid-cli
```

### 사용

```bash
# 단일 파일 변환
mmdc -i docs/diagrams/01-overall-system-flow.mmd -o docs/images/01-overall-system-flow.png

# 투명 배경
mmdc -i docs/diagrams/01-overall-system-flow.mmd -o docs/images/01-overall-system-flow.png -b transparent

# SVG로 변환
mmdc -i docs/diagrams/01-overall-system-flow.mmd -o docs/images/01-overall-system-flow.svg

# 모든 파일 일괄 변환 (PowerShell)
Get-ChildItem docs\diagrams\*.mmd | ForEach-Object {
    $basename = $_.BaseName
    mmdc -i $_.FullName -o "docs\images\$basename.png" -b transparent
}
```

**주의**: 한글 경로 문제로 인해 PowerShell에서 실행 시 오류가 발생할 수 있습니다.

---

## ⚠️ 문제 해결

### Mermaid Live Editor에서 다이어그램이 표시되지 않음

- 복사한 내용에 ```mermaid가 포함되어 있지 않은지 확인
- .mmd 파일은 순수 Mermaid 코드만 포함
- markdown 코드 블록 제거 필요

### 한글이 깨져서 표시됨

- Mermaid Live Editor는 UTF-8을 기본으로 지원하므로 문제없음
- 로컬 CLI 사용 시에만 발생 가능

### 이미지 해상도가 낮음

- Mermaid Live Editor: Actions → Configuration → Width 조정
- CLI: `-w 1920` 옵션 추가

---

## 📚 참고 자료

- [Mermaid 공식 문서](https://mermaid.js.org/)
- [Mermaid Live Editor](https://mermaid.live/)
- [Mermaid CLI GitHub](https://github.com/mermaid-js/mermaid-cli)

---

**작성일**: 2024-12-28  
**버전**: 1.0.0


