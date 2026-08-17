# Vercel 배포 가이드

MoneyMate는 **Next.js 프론트 + FastAPI 백엔드** 두 덩어리라, Vercel에 **프로젝트 2개**(같은 저장소에서 Root Directory만 다르게)로 올린다.

```
[Vercel 프로젝트 A: frontend]  ──BACKEND_URL──▶  [Vercel 프로젝트 B: backend(FastAPI 서버리스)]
      Root: frontend/                                    Root: backend/
```

> 데이터: `demo_ledger.py`(실 은행내역 기반)는 git 제외라 배포엔 없음 → **자동으로 합성 mock 데이터**로 뜬다. 개인정보 없음.

---

## 1) 백엔드 배포 (프로젝트 B)

Vercel → **Add New… → Project** → 이 저장소(`MoneyMate`) import

- **Root Directory**: `backend`
- **Framework Preset**: Other (자동으로 `vercel.json`+Python 감지)
- **Environment Variables** (아래 추가):

| Key | Value |
|---|---|
| `LLM_PROVIDER` | `gemini` |
| `GEMINI_API_KEY` | (본인 키) |
| `GEMINI_MODEL` | `gemini-flash-lite-latest` |
| `GEMINI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta/openai/` |
| `DATABASE_URL` | `sqlite:////tmp/moneymate.db` |
| `DEMO_TODAY` | `2026-08-15` |
| `LIVE_DATE` | `false` |

**Deploy** → 나온 URL 확인 (예: `https://moneymate-api.vercel.app`)
→ `그URL/api/dashboard` 열어서 JSON 나오면 성공.

> ⚠️ 공개 데모라 아무나 쓰면 Gemini 쿼터가 소진돼요. 원치 않으면 `LLM_PROVIDER=mock` 으로 두면 규칙기반(무료)으로 동작.

## 2) 프론트 배포 (프로젝트 A)

Vercel → **Add New… → Project** → 같은 저장소 다시 import

- **Root Directory**: `frontend`
- **Framework Preset**: Next.js (자동)
- **Environment Variables**:

| Key | Value |
|---|---|
| `BACKEND_URL` | (1번에서 나온 백엔드 URL, 예: `https://moneymate-api.vercel.app`) |

**Deploy** → 프론트 URL 열면 끝. `/api/*` 는 `next.config` rewrites가 백엔드로 프록시한다(=브라우저는 프론트 도메인만 봄, CORS 걱정 없음).

---

## ⚠️ 알아둘 점 (서버리스 특성)

- 백엔드가 **서버리스 SQLite(`/tmp`)** 라, 콜드스타트 때 DB가 초기화된다.
  → **정산 기억·테스트 이벤트 같은 사용자 변경이 유지 안 될 수 있음** (첫 요청 때 합성 데이터로 재시드).
  둘러보기 데모엔 충분하지만, 상태를 계속 유지하려면 아래 업그레이드.
- **영속 DB로 업그레이드 (선택)**: [Neon](https://neon.tech)/Vercel Postgres 무료 티어 → 백엔드 `DATABASE_URL` 을 그 Postgres 주소로 바꾸면 끝(SQLAlchemy라 코드 변경 거의 없음, `psycopg` 드라이버만 requirements에 추가).
- 무료 티어 백엔드는 유휴 시 콜드스타트로 첫 응답이 느릴 수 있음.

## 로컬 실행 (참고)
```bash
# 백엔드
cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8000
# 프론트
cd frontend && npm run dev   # http://localhost:3000
```
