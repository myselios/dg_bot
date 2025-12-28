# Telegram 알림 설정 가이드

## 📋 개요

AI 트레이딩 봇의 실시간 알림을 Telegram으로 받을 수 있습니다.

**알림 종류**:

- 거래 실행 알림 (매수/매도)
- AI 판단 알림
- 에러 발생 알림
- 봇 상태 변경 알림
- 일일 리포트 (매일 오전 9시)

**소요 시간**: 약 10분

---

## 📱 Step 1: Telegram 봇 생성 (5분)

### 1-1. BotFather 검색

1. Telegram 앱 실행
2. 검색창에 `@BotFather` 입력
3. 공식 BotFather 선택 (파란색 체크마크 확인)

### 1-2. 새 봇 생성

1. `/newbot` 명령어 입력
2. BotFather가 봇 이름을 물어봅니다

```
Please choose a name for your bot.
```

3. 원하는 봇 이름 입력 (예: `My Trading Bot`)

### 1-3. 봇 사용자명 설정

1. BotFather가 봇 사용자명을 물어봅니다

```
Now choose a username for your bot. It must end in `bot`.
```

2. 사용자명 입력 (끝에 `bot` 필수)
   - 예: `my_trading_alert_bot`
   - 예: `btc_trading_bot_2024`

### 1-4. Bot Token 복사

성공하면 다음과 같은 메시지가 표시됩니다:

```
Done! Congratulations on your new bot. You will find it at t.me/my_trading_alert_bot.
You can now add a description, about section and profile picture for your bot.

Use this token to access the HTTP API:
123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567890

For a description of the Bot API, see this page: https://core.telegram.org/bots/api
```

**중요**: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567890` 형식의 Token을 복사하세요!

---

## 🔑 Step 2: Chat ID 확인 (3분)

### 2-1. 봇에게 메시지 전송

1. BotFather 메시지의 `t.me/your_bot_username` 링크 클릭
2. `/start` 메시지 전송
3. 아무 메시지나 추가로 전송 (예: "안녕")

### 2-2. Chat ID 조회

다음 방법 중 하나를 선택하세요:

#### 방법 A: 웹 브라우저 사용 (권장)

1. 아래 URL을 복사하여 브라우저 주소창에 붙여넣기
2. `<YOUR_BOT_TOKEN>`을 실제 Bot Token으로 교체

```
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
```

**예시**:

```
https://api.telegram.org/bot123456789:ABCdefGHIjklMNOpqrsTUVwxyz/getUpdates
```

3. 브라우저에서 JSON 응답 확인

```json
{
  "ok": true,
  "result": [
    {
      "update_id": 123456789,
      "message": {
        "message_id": 1,
        "from": {
          "id": 987654321,
          "is_bot": false,
          "first_name": "Your Name"
        },
        "chat": {
          "id": 987654321,  ← 이 값이 Chat ID입니다!
          "first_name": "Your Name",
          "type": "private"
        },
        "date": 1234567890,
        "text": "/start"
      }
    }
  ]
}
```

4. `"chat"` → `"id"` 값을 복사하세요 (예: `987654321`)

#### 방법 B: PowerShell 사용 (Windows)

```powershell
$token = "YOUR_BOT_TOKEN"
Invoke-RestMethod -Uri "https://api.telegram.org/bot$token/getUpdates" | ConvertTo-Json -Depth 10
```

#### 방법 C: curl 사용 (Linux/Mac)

```bash
curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
```

---

## ⚙️ Step 3: .env 파일 설정 (2분)

### 3-1. .env 파일 열기

프로젝트 루트 디렉토리의 `.env` 파일을 엽니다.

```bash
# Windows
notepad .env

# Linux/Mac
nano .env
```

### 3-2. Telegram 설정 추가/수정

`.env` 파일에 다음 내용을 추가하거나 수정합니다:

```env
# Telegram Bot 설정
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz  # 실제 토큰으로 교체
TELEGRAM_CHAT_ID=987654321  # 실제 Chat ID로 교체
```

**주의사항**:

- ❌ 따옴표 사용 금지: `TELEGRAM_BOT_TOKEN="123..."`
- ✅ 따옴표 없이 입력: `TELEGRAM_BOT_TOKEN=123...`
- ✅ `TELEGRAM_ENABLED=true`로 설정 (알림 활성화)

### 3-3. 파일 저장

- Windows (메모장): `Ctrl + S`
- Linux/Mac (nano): `Ctrl + O` → `Enter` → `Ctrl + X`

---

## 🚀 Step 4: 스케줄러 재시작 및 테스트

### 4-1. Docker 환경에서 재시작

```bash
# Docker Compose로 스케줄러 재시작
docker-compose -f docker-compose.full-stack.yml restart scheduler

# 로그 확인
docker-compose -f docker-compose.full-stack.yml logs scheduler -f
```

### 4-2. 로컬 환경에서 재시작

#### Windows (PowerShell)

```powershell
# 인코딩 수정 스크립트 먼저 실행
.\fix-encoding.ps1

# 스케줄러 시작
.\start-scheduler.ps1
```

#### Linux/Mac

```bash
# 스케줄러 시작
./start-scheduler.sh
```

### 4-3. 알림 수신 확인

스케줄러가 시작되면 **즉시** Telegram으로 다음과 같은 알림을 받아야 합니다:

```
▶️ 봇 상태 변경

📌 상태: STARTED
📝 메시지: 스케줄러가 시작되었습니다. (주기: 1시간)

🕐 시각: 2025-12-28 14:30:00
```

**알림을 받지 못한 경우** → [트러블슈팅](#-트러블슈팅) 섹션 참고

---

## ✅ 성공 확인 체크리스트

- [ ] Telegram 봇 생성 완료
- [ ] Bot Token 확보
- [ ] Chat ID 확보
- [ ] `.env` 파일 설정 완료
- [ ] 스케줄러 재시작 완료
- [ ] 봇 시작 알림 수신 확인
- [ ] 로그에 "Telegram 알림 전송 완료" 메시지 확인

---

## 📊 알림 예시

### 1. 거래 실행 알림

```
💰 매수 거래 실행

📊 심볼: KRW-BTC
💵 가격: 95,000,000 KRW
📦 수량: 0.01000000
💰 총액: 950,000 KRW

🕐 시각: 2025-12-28 10:00:00

🤖 AI 판단: 단기 상승 추세 감지. RSI 과매도 구간. 매수 타이밍 적합.
```

### 2. 에러 발생 알림

```
⚠️ 에러 발생

🔴 타입: APIError
📝 메시지: Upbit API 호출 실패

🕐 시각: 2025-12-28 11:30:00

상세 정보:
  • job: trading_job
  • ticker: KRW-BTC
```

### 3. 일일 리포트 (매일 오전 9시)

```
📊 일일 트레이딩 리포트

📈 수익률: +1.50%
💰 수익/손실: +15,000 KRW
📦 거래 횟수: 24회
💵 현재 자산: 1,015,000 KRW

📅 날짜: 2025-12-28
```

---

## 🛠 트러블슈팅

### Q1. 알림이 전혀 오지 않아요

**원인**: Bot Token 또는 Chat ID가 잘못되었을 가능성

**해결 방법**:

1. **로그 확인**:

   ```bash
   # Docker
   docker-compose -f docker-compose.full-stack.yml logs scheduler | grep Telegram

   # 로컬
   Get-Content logs\scheduler\scheduler.log | Select-String "Telegram"
   ```

2. **Bot Token 재확인**:

   - BotFather에서 `/token` 명령어로 토큰 재확인
   - `.env` 파일에 복사할 때 공백이 없는지 확인

3. **Chat ID 재확인**:

   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```

   - `/start` 메시지를 다시 전송한 후 재조회

4. **수동 테스트** (Python):

   ```python
   # venv 활성화 후 실행
   .\venv\Scripts\Activate.ps1

   # Python 코드 실행
   python -c "
   import asyncio
   import os
   from telegram import Bot

   async def test():
       token = 'YOUR_BOT_TOKEN'
       chat_id = 'YOUR_CHAT_ID'
       bot = Bot(token=token)
       await bot.send_message(chat_id=chat_id, text='테스트 메시지')
       print('전송 완료')

   asyncio.run(test())
   "
   ```

---

### Q2. "Telegram 알림 비활성화" 로그가 표시돼요

**원인**: `TELEGRAM_ENABLED=false` 또는 환경변수가 로드되지 않음

**해결 방법**:

1. `.env` 파일 확인:

   ```bash
   cat .env | grep TELEGRAM_ENABLED
   ```

2. `TELEGRAM_ENABLED=true`로 설정되어 있는지 확인

3. Docker 환경인 경우:

   ```bash
   # 컨테이너 환경변수 확인
   docker exec trading_bot_scheduler env | grep TELEGRAM

   # 재빌드 및 재시작
   docker-compose -f docker-compose.full-stack.yml build scheduler
   docker-compose -f docker-compose.full-stack.yml restart scheduler
   ```

---

### Q3. "Unauthorized" 에러가 발생해요

**원인**: Bot Token이 잘못되었습니다.

**해결 방법**:

1. BotFather에서 `/mybots` 선택
2. 생성한 봇 선택 → `API Token` 클릭
3. 토큰 복사 후 `.env` 파일 업데이트
4. 스케줄러 재시작

---

### Q4. "Chat not found" 에러가 발생해요

**원인**: Chat ID가 잘못되었거나, 봇과 대화를 시작하지 않았습니다.

**해결 방법**:

1. Telegram 앱에서 봇 검색 (`@your_bot_username`)
2. `/start` 메시지 전송
3. Chat ID 재확인:

   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```

4. `.env` 파일 업데이트
5. 스케줄러 재시작

---

### Q5. 알림이 늦게 도착해요

**정상 동작**: Telegram Bot API는 보통 1-3초 내에 메시지를 전송합니다.

**지연이 5초 이상인 경우**:

1. 네트워크 연결 확인
2. Telegram 서버 상태 확인: https://telegram.org/status
3. 로그에서 "Telegram 메시지 전송 성공" 시간 확인

---

## 🔒 보안 주의사항

### ⚠️ Bot Token 보호

Bot Token은 **절대 공개하지 마세요**!

- ❌ GitHub에 `.env` 파일 커밋 금지
- ❌ 공개 채팅방/포럼에 토큰 게시 금지
- ✅ `.gitignore`에 `.env` 포함 확인
- ✅ Token이 유출된 경우 BotFather에서 `/revoke` 명령으로 즉시 폐기

### 🔐 Chat ID 보호

- Chat ID는 개인 식별 가능 정보입니다.
- 다른 사람과 공유하지 마세요.

### 🛡️ 봇 사용 권한

- BotFather 설정에서 다음 권한을 제한하세요:
  - ✅ 메시지 전송만 허용
  - ❌ 그룹 추가 비활성화
  - ❌ 인라인 모드 비활성화

**설정 방법**:

1. BotFather → `/mybots`
2. 봇 선택 → `Bot Settings` → `Group Privacy`
3. `Disable`로 설정

---

## 📚 추가 정보

### 알림 메시지 커스터마이징

알림 메시지를 수정하려면 다음 파일을 편집하세요:

**파일**: `backend/app/services/notification.py`

```python
async def notify_trade(self, symbol: str, side: str, ...):
    emoji = "💰" if side == "buy" else "💸"
    message = f"""
{emoji} <b>{side_kr} 거래 실행</b>
...
"""
```

### 알림 주기 조정

**거래 알림**: 매수/매도 발생 시 즉시 전송
**일일 리포트**: 매일 오전 9시 전송

일일 리포트 시간을 변경하려면:

**파일**: `backend/app/core/scheduler.py`

```python
scheduler.add_job(
    daily_report_job,
    trigger=CronTrigger(hour=9, minute=0, timezone="Asia/Seoul"),  # 9시 → 원하는 시간으로 변경
    ...
)
```

### 알림 비활성화

임시로 알림을 중지하려면:

```env
# .env 파일
TELEGRAM_ENABLED=false
```

스케줄러 재시작 필요.

---

## 🎓 참고 자료

- [Telegram Bot API 공식 문서](https://core.telegram.org/bots/api)
- [python-telegram-bot 라이브러리](https://python-telegram-bot.org/)
- [BotFather 명령어 목록](https://core.telegram.org/bots#6-botfather)

---

**작성일**: 2025-12-28  
**최종 업데이트**: 2025-12-28  
**관련 문서**: `docs/MONITORING_IMPLEMENTATION_PLAN.md`
