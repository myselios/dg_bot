# 🚀 GitHub 저장소 업로드 빠른 가이드

## ⚡ 3단계로 완료하기

### 1단계: GitHub에서 저장소 생성

1. https://github.com/new 방문
2. Repository name: `dg_bot`
3. Description: `비트코인 자동 트레이딩 봇`
4. Public 선택
5. **"Initialize this repository with a README" 체크 해제** ❌
6. "Create repository" 클릭

### 2단계: Personal Access Token 생성

1. GitHub Settings > Developer settings > Personal access tokens > Tokens (classic)
2. "Generate new token" 클릭
3. Note: `dg_bot_access`
4. Scopes: `repo` 체크 ✅
5. "Generate token" 클릭
6. **생성된 토큰을 복사** (다시 볼 수 없음!)

### 3단계: 코드 푸시

#### 방법 A: PowerShell 스크립트 (간편)

```powershell
.\push-to-github.ps1
```

스크립트 실행 시:
- GitHub 사용자명 입력
- 자동으로 Git 초기화 및 푸시
- 인증 시 Personal Access Token 사용

#### 방법 B: 수동 명령어

```bash
# Git 초기화
git init
git add .
git commit -m "Initial commit: DG Trading Bot"

# 원격 저장소 연결 (YOUR_USERNAME을 실제 사용자명으로 변경)
git remote add origin https://github.com/YOUR_USERNAME/dg_bot.git

# 푸시
git push -u origin main
```

**인증:**
- Username: GitHub 사용자명
- Password: Personal Access Token (위에서 생성한 토큰)

---

## ✅ 완료 확인

푸시 성공 후:
1. https://github.com/YOUR_USERNAME/dg_bot 방문
2. 코드가 업로드되었는지 확인

---

## 📚 상세 가이드

더 자세한 내용은 [docs/GITHUB_SETUP_GUIDE.md](./docs/GITHUB_SETUP_GUIDE.md) 참고

---

## 🆘 문제 해결

### 인증 실패
- 비밀번호가 아닌 Personal Access Token 사용
- Token의 `repo` 권한 확인

### 원격 저장소 오류
```bash
git remote remove origin
git remote add origin https://github.com/YOUR_USERNAME/dg_bot.git
```

### 한글 경로 오류 (Windows)
- `push-to-github.ps1` 스크립트 사용 (자동 처리)



