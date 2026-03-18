# NPC Dialogue Engine v0.2 — Production Infrastructure 변경 내역

> **커밋**: `e23f18e` | **날짜**: 2026-03-18 | **변경 파일**: 29개 (+2,354줄)

---

## 개요

포트폴리오 프레젠테이션을 위한 프로덕션 수준 인프라 레이어를 추가했습니다.
보안, 관측성, 복원력, API 품질, DevOps 5개 영역을 커버합니다.

---

## 1. 보안 (Security)

### Rate Limiting — `src/api/rate_limiter.py`
- **알고리즘**: 슬라이딩 윈도우 카운터 (in-memory)
- **기본 설정**: 60 requests / 60 seconds (IP별)
- 초과 시 `429 Too Many Requests` + `Retry-After` 헤더
- `/health`, `/metrics`, `/docs` 등 모니터링 경로는 제외
- 설정: `RATE_LIMIT_MAX_REQUESTS`, `RATE_LIMIT_WINDOW_SECONDS` 환경변수

### Security Headers — `src/api/middleware.py`
| 헤더 | 값 | 목적 |
|------|----|------|
| `X-Content-Type-Options` | `nosniff` | MIME 스니핑 방지 |
| `X-Frame-Options` | `DENY` | 클릭재킹 방지 |
| `X-XSS-Protection` | `1; mode=block` | XSS 필터 활성화 |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | 리퍼러 누출 제한 |
| `Permissions-Policy` | `camera=(), microphone=()` | 브라우저 기능 제한 |
| `Cache-Control` | `no-store, no-cache` | 민감 데이터 캐싱 방지 |

### Admin API Key — `src/api/routes/admin.py`
- `X-API-Key` 헤더 기반 인증
- `ADMIN_API_KEY` 환경변수 (빈 값 = 개발 모드, 인증 없음)
- `secrets.compare_digest()` 사용 (타이밍 공격 방지)
- admin 라우터 전체에 `Depends` 로 적용

### CORS 강화 — `src/api/main.py`
- `allow_origins=["*"]` → 환경변수 기반 화이트리스트
- `CORS_ORIGINS=http://localhost:5173,http://localhost:3000`
- HTTP 메서드도 `GET/POST/PUT/DELETE/OPTIONS` 만 허용

### GZip 압축 — `src/api/middleware.py`
- Starlette `GZipMiddleware` 적용
- 500바이트 이상 응답 자동 압축

---

## 2. 관측성 (Observability)

### Prometheus 메트릭 — `src/api/metrics.py` + `src/api/routes/monitoring.py`
외부 의존성 없이 자체 구현한 메트릭 시스템:

| 메트릭 | 타입 | 라벨 |
|--------|------|------|
| `http_requests_total` | counter | method, path, status |
| `http_request_duration_seconds` | histogram | method, path |
| `websocket_connections_active` | gauge | npc_id |
| `dialogue_pipeline_duration_seconds` | histogram | npc_id |

- `GET /metrics` — Prometheus text exposition format
- 히스토그램 버킷: 5ms ~ 10s (11단계)
- 경로 정규화로 카디널리티 제어 (동적 세그먼트 → 템플릿 변수)

### Structured JSON Logging — `src/api/logging_config.py`
```json
{
  "timestamp": "2026-03-18T12:00:00+00:00",
  "level": "INFO",
  "logger": "src.api.middleware",
  "message": "[a1b2c3d4] -> GET /health from 127.0.0.1",
  "module": "middleware",
  "function": "dispatch",
  "line": 48
}
```
- `LOG_FORMAT=json` (기본) 또는 `LOG_FORMAT=text` (개발용)
- `LOG_LEVEL` 환경변수로 제어
- noisy 라이브러리 자동 suppression (uvicorn.access, chromadb 등)

### Correlation ID — `src/api/middleware.py`
- 모든 요청에 `X-Request-ID` UUID 자동 부여
- 클라이언트가 제공한 ID는 그대로 사용 (분산 추적 연계)
- 로그에 `[request_id[:8]]` 포함
- 에러 응답에도 `request_id` 포함

### Enhanced Health Check — `GET /health/detailed`
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "npcs_loaded": 4,
  "dependencies": {
    "redis": {"status": "healthy", "latency_ms": 1.23},
    "postgresql": {"status": "healthy", "latency_ms": 5.67},
    "chromadb": {"status": "healthy", "document_count": 150, "latency_ms": 12.34}
  },
  "circuit_breakers": {
    "redis": {"name": "redis", "state": "closed", "failure_count": 0},
    "postgresql": {"name": "postgresql", "state": "closed", "failure_count": 0},
    "llm_api": {"name": "llm_api", "state": "closed", "failure_count": 0}
  }
}
```

### Monitoring Stack — `docker-compose.yml`
- **Prometheus** (`:9090`) — 15초 간격 스크래핑, 7일 데이터 보존
- **Grafana** (`:3000`) — Prometheus 데이터소스 자동 프로비저닝

---

## 3. 복원력 (Resilience)

### Circuit Breaker — `src/api/circuit_breaker.py`
3개 서비스별 사전 구성된 인스턴스:

| 서비스 | failure_threshold | recovery_timeout |
|--------|-------------------|-----------------|
| Redis | 3 | 15초 |
| PostgreSQL | 3 | 30초 |
| LLM API | 5 | 60초 |

상태 머신: `CLOSED → OPEN → HALF_OPEN → CLOSED`

### LLM Retry — `src/npc/dialogue.py`
- **최대 3회 재시도** + exponential backoff (1s → 2s → 4s)
- **Jitter** 추가로 thundering herd 방지
- Circuit breaker 연동 (OPEN 상태면 즉시 실패)
- 모든 재시도 실패 시 NPC 캐릭터별 폴백 응답

### WebSocket Heartbeat — `src/api/routes/chat.py`
- 30초 간격 `{"type": "ping"}` 전송
- 클라이언트 `{"type": "pong"}` 응답 대기
- 40초(30+10) 무응답 시 자동 연결 종료
- 일반 메시지도 활성 상태로 인정

---

## 4. API 품질 (API Quality)

### Pagination — `src/api/schemas.py`
```python
PaginatedResponse[T]  # Generic 타입
```
- `skip` / `limit` 파라미터 (기본: 0 / 20)
- `has_more` 필드로 다음 페이지 존재 여부 표시
- NPC 목록, Quest 목록 엔드포인트에 적용
- Quest 목록에 `status_filter` 파라미터 추가

### 표준 에러 응답 — `src/api/exceptions.py`
```json
{
  "error": {
    "code": "NPC_NOT_FOUND",
    "message": "NPC 'unknown_npc' not found.",
    "request_id": "a1b2c3d4-..."
  }
}
```
에러 코드 카탈로그:
- `VALIDATION_ERROR`, `NPC_NOT_FOUND`, `QUEST_NOT_FOUND`
- `RATE_LIMITED`, `UNAUTHORIZED`, `FORBIDDEN`
- `INTERNAL_ERROR`, `LLM_UNAVAILABLE`, `SERVICE_DEGRADED`

글로벌 핸들러:
- `APIError` → 커스텀 에러
- `HTTPException` → FastAPI 기본 에러 래핑
- `RequestValidationError` → Pydantic 검증 실패 (필드별 상세)

---

## 5. DevOps

### GitHub Actions CI — `.github/workflows/ci.yml`
3개 Job (lint → test / docker-build 병렬):
1. **lint**: ruff check + ruff format --check
2. **test**: pip install → pytest (mocked external services)
3. **docker-build**: Docker Buildx with GHA cache

### Alembic Migration — `alembic/`
- Async PostgreSQL (asyncpg) 지원
- `alembic upgrade head` — 마이그레이션 실행
- `alembic revision --autogenerate -m "..."` — 자동 생성
- 초기 마이그레이션: 7개 테이블 + 6개 인덱스
- URL은 `src.config.settings`에서 런타임 로드

### Makefile
```
make install     — 의존성 설치 + pre-commit 설정
make dev         — Docker Compose 전체 실행
make test        — pytest 실행
make lint        — ruff 검사
make format      — 자동 포맷팅
make migrate     — DB 마이그레이션
make ingest      — 월드빌딩 문서 임베딩
make evaluate    — RAG 평가 파이프라인
make clean       — 캐시/빌드 정리
```

### Pre-commit — `.pre-commit-config.yaml`
- ruff lint + format
- trailing whitespace, end-of-file-fixer
- check-yaml, check-json
- check-added-large-files (500KB)
- detect-private-key

### 기타
- `pyproject.toml`: ruff 설정, pytest 설정, build-backend 수정
- `.env.example`: 신규 환경변수 문서화

---

## 신규 파일 목록 (17개)

```
.github/workflows/ci.yml                          — CI/CD 파이프라인
.pre-commit-config.yaml                            — Pre-commit 훅
Makefile                                           — 개발 편의 명령어
alembic.ini                                        — Alembic 설정
alembic/env.py                                     — Async 마이그레이션 환경
alembic/script.py.mako                             — 마이그레이션 템플릿
alembic/versions/001_initial_schema.py             — 초기 스키마
monitoring/prometheus.yml                          — Prometheus 스크래핑 설정
monitoring/grafana/provisioning/datasources/       — Grafana 데이터소스
src/api/rate_limiter.py                            — Rate Limiting 미들웨어
src/api/metrics.py                                 — Prometheus 메트릭
src/api/logging_config.py                          — JSON 로깅 설정
src/api/circuit_breaker.py                         — Circuit Breaker
src/api/retry.py                                   — Retry 데코레이터
src/api/exceptions.py                              — 표준 에러 응답
src/api/routes/monitoring.py                       — /health/detailed + /metrics
tests/test_middleware.py                           — 인프라 테스트
```

## 수정 파일 목록 (12개)

```
src/api/main.py            — 라우터/핸들러 등록, CORS, 로깅 초기화
src/api/middleware.py       — Security Headers, GZip, Correlation ID
src/api/routes/admin.py     — API Key 인증
src/api/routes/chat.py      — Heartbeat, 메트릭, retry 연동
src/api/routes/npc.py       — Pagination
src/api/routes/quest.py     — Pagination + status filter
src/api/schemas.py          — PaginatedResponse[T] 제네릭
src/config.py               — 신규 설정값
src/npc/dialogue.py         — LLM retry + circuit breaker
pyproject.toml              — ruff/pytest/build 설정
docker-compose.yml          — Prometheus + Grafana
.env.example                — 신규 환경변수
```

---

## 아키텍처 미들웨어 스택 (실행 순서)

```
Request
  │
  ▼
GZipMiddleware              ← 응답 압축
  │
  ▼
ErrorHandlingMiddleware     ← 예외 → JSON 에러
  │
  ▼
SecurityHeadersMiddleware   ← OWASP 보안 헤더
  │
  ▼
RateLimitMiddleware         ← IP별 요청 제한
  │
  ▼
MetricsMiddleware           ← Prometheus 카운터/히스토그램
  │
  ▼
RequestLoggingMiddleware    ← Correlation ID + 로깅
  │
  ▼
Route Handler               ← 비즈니스 로직
```
