# 🗡️ NPC Dialogue Engine

> **RAG 기반 게임 NPC 동적 대화 시스템** — 세계관 충실성을 유지하면서 감정·호감도·퀘스트가 연동되는 개인화된 NPC 대화 경험

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-WebSocket-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/LangChain-RAG_Pipeline-1C3C3C?logo=langchain&logoColor=white)](https://langchain.com)
[![Docker](https://img.shields.io/badge/Docker-One--Click_Deploy-2496ED?logo=docker&logoColor=white)](https://docker.com)
[![React](https://img.shields.io/badge/React-TypeScript-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📌 프로젝트 동기

기존 게임 NPC 대화 시스템의 한계:

| 기존 방식 | 문제점 |
|-----------|--------|
| 고정 스크립트 | 반복적이고 몰입감 저하 |
| 단순 키워드 매칭 | 자연스러운 대화 불가 |
| 세계관 무시 | 할루시네이션 · 캐릭터 이탈 |
| 상태 비연동 | 감정/호감도/퀘스트 반영 불가 |

**→ LLM + RAG + 게임 시스템 연동으로 "진짜 살아있는 NPC"를 구현합니다.**

---

## 🏗️ 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React + TypeScript)            │
│   ChatWindow │ NPCProfile │ QuestPanel │ WorldMap               │
└──────────┬──────────────────────────────────────────────────────┘
           │ WebSocket (실시간 스트리밍)
           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                              │
│                                                                 │
│  ┌──────────── 8-Step Dialogue Pipeline ──────────────┐        │
│  │                                                     │        │
│  │  ① Security Filter ──→ 3단계 프롬프트 인젝션 방어   │        │
│  │          │                                          │        │
│  │  ② Intent Classifier ──→ 8종 의도 + 감성 분석      │        │
│  │          │                                          │        │
│  │  ③ RAG Retrieval ──→ 의도별 소스 라우팅             │        │
│  │          │         ┌─────────────────────┐          │        │
│  │          │         │  Hybrid Search      │          │        │
│  │          │         │  Vector 70% + BM25  │          │        │
│  │          │         │  + Cross-Encoder    │          │        │
│  │          │         │    Reranking        │          │        │
│  │          │         └─────────────────────┘          │        │
│  │  ④ Emotion Update ──→ 7종 감정 상태 머신            │        │
│  │          │                                          │        │
│  │  ⑤ Response Generation ──→ 페르소나 기반 응답       │        │
│  │          │                                          │        │
│  │  ⑥ Persona Validation ──→ 캐릭터 일관성 검증       │        │
│  │          │                                          │        │
│  │  ⑦ Affinity Update ──→ 5단계 호감도 반영            │        │
│  │          │                                          │        │
│  │  ⑧ Quest Trigger ──→ 대화 내 퀘스트 감지            │        │
│  │                                                     │        │
│  └─────────────────────────────────────────────────────┘        │
└──────┬──────────────┬───────────────┬───────────────────────────┘
       │              │               │
       ▼              ▼               ▼
┌──────────┐  ┌──────────────┐  ┌──────────────┐
│ ChromaDB │  │    Redis     │  │ PostgreSQL   │
│ 벡터 저장 │  │ 단기 기억    │  │ 장기 기억    │
│ + BM25   │  │ 시맨틱 캐시  │  │ 호감도/퀘스트│
└──────────┘  └──────────────┘  └──────────────┘
       ▲
       │
┌──────────────────────────┐
│   Worldbuilding Content  │
│  NPC · Lore · Quest · Item│
│      (Markdown Files)    │
└──────────────────────────┘
```

---

## ✨ 핵심 기능

### 1. 하이브리드 RAG 파이프라인

의미 검색과 키워드 검색을 결합하여 **게임 세계관에 충실한 응답**을 생성합니다.

```
Query: "가론이 만든 검 중에 가장 유명한 건?"

┌─────────────────────────────────────────────┐
│           Hybrid Retrieval                   │
│                                              │
│  Vector Search (70%)     BM25 Search (30%)   │
│  multilingual-e5-large   Kiwi 형태소 분석     │
│         │                      │             │
│         └──────┬───────────────┘             │
│                ▼                              │
│       Cross-Encoder Reranking                │
│  ms-marco-multilingual-MiniLM-L12-v2         │
│                │                              │
│                ▼                              │
│       Top-K Context Selection                │
└─────────────────────────────────────────────┘
```

- **의도별 소스 라우팅**: 퀘스트 질문 → `quests/`, 로어 질문 → `lore/`, NPC 질문 → `npcs/`
- **문서 유형별 청킹**: NPC 프로필은 섹션별, 퀘스트는 단계별, 아이템은 개별 분리
- **시맨틱 캐시**: 유사도 0.95 이상 쿼리는 Redis 캐시에서 즉시 응답 (LLM 호출 절감)

### 2. NPC 감정 상태 머신

7종 감정 × 쿨다운 × 턴 기반 감쇠로 **자연스러운 감정 흐름**을 구현합니다.

```
              ┌─── EXCITED ◄── 호의적 반복 ───┐
              │                                │
NEUTRAL ──────┼─── HAPPY ◄── 친절한 대화       │
   ▲          │                                │
   │ (감쇠)   ├─── ANNOYED ◄── 반복 질문       │
   │          │                                │
   └──────────┼─── SAD ◄── 슬픈 화제           │
              │                                │
              ├─── ANGRY ◄── 도발/모욕         │
              │                                │
              └─── SUSPICIOUS ◄── 인젝션 시도  │

• Light 감정 (HAPPY, ANNOYED): 3턴 후 자동 감쇠
• Heavy 감정 (ANGRY, SAD): 5턴 후 자동 감쇠
• 쿨다운: 동일 트리거 3턴 내 반복 시 효과 -50%, 5턴 내 -100%
```

### 3. 5단계 호감도 시스템

NPC와의 관계가 깊어질수록 **새로운 콘텐츠와 혜택이 잠금 해제**됩니다.

| 단계 | 범위 | 명칭 | 잠금 해제 콘텐츠 |
|------|------|------|-----------------|
| 1 | 0–20 | 낯선 사람 | 기본 대화만 |
| 2 | 21–40 | 아는 사이 | 기본 힌트 제공 |
| 3 | 41–60 | 친구 | 비밀 정보 + 할인 |
| 4 | 61–80 | 절친 | 히든 퀘스트 개방 |
| 5 | 81–100 | 맹우 | 동행 가능 + 전체 해금 |

### 4. 스포일러 방지 힌트 엔진

퀘스트 진행률에 따라 **적절한 수준의 힌트**만 제공합니다.

```
진행률  0% ──────── 30% ──────── 60% ──────── 100%
힌트    minimal     basic       medium      detailed
        "그건       "서쪽       "폐광 2층    "마지막 방의
         위험한      광산을      오른쪽       레버를
         곳이지"     찾아봐"     통로야"      당겨봐"
```

### 5. 3단계 프롬프트 인젝션 방어

NPC 캐릭터를 유지하면서 악의적 입력을 차단합니다.

```
사용자 입력
    │
    ▼
┌─ Stage 1: Rule-Based Filter ─┐
│  정규식 패턴 매칭 (즉시 차단)  │
└───────────┬───────────────────┘
            │ pass
            ▼
┌─ Stage 2: LLM Classification ─┐
│  컨텍스트 기반 위협 분석        │
└───────────┬────────────────────┘
            │ pass
            ▼
┌─ Stage 3: Output Validation ──┐
│  응답의 캐릭터 이탈 여부 검증   │
└───────────┬────────────────────┘
            │
            ▼
    ✅ 안전한 응답 전송

차단 시: NPC 캐릭터에 맞는 거부 응답
  가론: "허, 대장장이한테 그런 수작이 통할 것 같나?"
  엘라라: "...흥미로운 마법이군. 하지만 내겐 안 통해."
```

### 6. Cross-NPC 메모리

NPC 간 정보가 공유되어 **살아있는 세계관**을 연출합니다.

```
[플레이어 → 가론] "마녀의 숲에서 돌아왔어"
[가론] "엘라라 그 친구, 무사한 거겠지?"

         ┌─ Redis ─────────────┐
         │ Short-term Memory   │
         │ 최근 20턴, TTL 30분  │
         └─────────┬───────────┘
                   │ 세션 종료 시 요약
                   ▼
         ┌─ PostgreSQL ────────┐
         │ Long-term Memory    │
         │ LLM 요약 + 영구 저장 │
         │ Cross-NPC 공유      │
         └─────────────────────┘
```

---

## 🛠️ 기술 스택

| 카테고리 | 기술 | 선택 근거 |
|----------|------|-----------|
| **LLM** | Gemini 2.0 Flash | 비용 효율 + 한국어 성능 + 빠른 응답 |
| **RAG Framework** | LangChain | EnsembleRetriever + LangSmith 네이티브 지원 |
| **Embedding** | multilingual-e5-large | MTEB 한국어 벤치마크 상위권 + 다국어 지원 |
| **Vector DB** | ChromaDB | 로컬 개발 무서버 + Pinecone 교체 가능 추상화 |
| **BM25** | rank-bm25 + Kiwi | pip 설치만으로 한국어 형태소 분석 (Mecab 대비 설치 용이) |
| **Reranker** | ms-marco-MiniLM-L12-v2 | 다국어 Cross-Encoder, 정밀 재정렬 |
| **Backend** | FastAPI + WebSocket | 실시간 토큰 스트리밍, 비동기 처리 |
| **Cache/Session** | Redis 7 | 단기 기억 + 시맨틱 캐시를 단일 인프라로 |
| **Database** | PostgreSQL 16 | 장기 기억 + 호감도/퀘스트 상태 영속화 |
| **Frontend** | React + TypeScript + Vite | 타입 안전성 + 빠른 개발 |
| **Container** | Docker Compose | 4개 서비스 원클릭 배포 |
| **Monitoring** | LangSmith (optional) | LLM 호출 추적 + 프롬프트 디버깅 |

---

## 🚀 Quick Start

### 사전 요구사항

- Docker & Docker Compose
- Gemini API Key ([Google AI Studio](https://aistudio.google.com/))

### 실행

```bash
# 1. 클론
git clone https://github.com/your-username/npc-dialogue-engine.git
cd npc-dialogue-engine

# 2. 환경변수 설정
cp .env.example .env
# .env 파일에 GEMINI_API_KEY 입력

# 3. 원클릭 실행
docker-compose up --build

# API Docs:  http://localhost:8000/docs
# Chat UI:   http://localhost:5173
```

### CLI 데모

```bash
# 가론(대장장이)과 대화
python scripts/demo.py --npc garon

# 엘라라(마녀)와 대화
python scripts/demo.py --npc elara

# 평가 실행
python scripts/evaluate.py

# 세계관 문서 인제스트
python scripts/ingest.py
```

---

## 📁 프로젝트 구조

```
npc-dialogue-engine/
│
├── src/
│   ├── api/                          # FastAPI 백엔드
│   │   ├── main.py                   # 앱 팩토리 + 라이프사이클
│   │   ├── guard.py                  # 3단계 프롬프트 인젝션 방어
│   │   ├── schemas.py                # Pydantic 요청/응답 모델
│   │   └── routes/
│   │       ├── chat.py               # WebSocket /ws/chat/{npc_id}
│   │       ├── npc.py                # NPC 정보 엔드포인트
│   │       ├── quest.py              # 퀘스트 상태 엔드포인트
│   │       └── admin.py              # 관리자 (세계관 리로드)
│   │
│   ├── npc/                          # NPC 대화 & 상태 시스템
│   │   ├── dialogue.py               # 8단계 대화 파이프라인 오케스트레이터
│   │   ├── persona.py                # NPC 페르소나 로더 (마크다운 파싱)
│   │   ├── emotion.py                # 감정 상태 머신 (7종 + 쿨다운/감쇠)
│   │   ├── affinity.py               # 호감도 매니저 (0-100, 5단계)
│   │   ├── intent.py                 # 의도 분류기 (8종 + 감성 분석)
│   │   └── memory.py                 # 메모리 매니저 (단기/장기/Cross-NPC)
│   │
│   ├── rag/                          # RAG 파이프라인
│   │   ├── retriever.py              # 하이브리드 검색 (Vector + BM25)
│   │   ├── ingestion.py              # 세계관 문서 인제스트
│   │   ├── chunker.py                # 문서 유형별 청킹
│   │   ├── reranker.py               # Cross-Encoder 리랭킹
│   │   ├── cache.py                  # 시맨틱 캐시 (Redis)
│   │   └── evaluator.py              # RAG 품질 평가
│   │
│   ├── quest/                        # 퀘스트 시스템
│   │   ├── tracker.py                # 퀘스트 진행 관리
│   │   ├── hint_engine.py            # 스포일러 방지 힌트 엔진
│   │   └── trigger.py                # 대화 내 퀘스트 트리거 감지
│   │
│   ├── db/                           # 데이터베이스 계층
│   │   ├── database.py               # SQLAlchemy 비동기 엔진
│   │   └── models.py                 # ORM 모델 (6개 테이블)
│   │
│   ├── evaluation/                   # 품질 평가 모듈
│   │   ├── persona_consistency.py    # 캐릭터 일관성 검사
│   │   ├── hallucination_check.py    # 세계관 충실도 검증
│   │   └── response_quality.py       # 응답 품질 메트릭
│   │
│   └── frontend/                     # React 프론트엔드
│       └── src/
│           ├── components/
│           │   ├── ChatWindow.tsx     # 채팅 UI
│           │   ├── NPCProfile.tsx     # NPC 감정/호감도 표시
│           │   ├── QuestPanel.tsx     # 퀘스트 진행 패널
│           │   └── WorldMap.tsx       # NPC 위치 맵
│           └── hooks/
│               └── useWebSocket.ts    # WebSocket 연결 훅
│
├── worldbuilding/                    # 게임 세계관 콘텐츠
│   ├── npcs/                         # NPC 프로필 (4종)
│   │   ├── blacksmith_garon.md       # 대장장이 가론 (52세, 마스터 대장장이)
│   │   ├── witch_elara.md            # 마녀 엘라라
│   │   ├── merchant_rico.md          # 상인 리코
│   │   └── guard_captain_thane.md    # 경비대장 테인
│   ├── lore/                         # 세계 설정 (역사, 세력, 지리, 마법)
│   ├── quests/                       # 퀘스트 (메인 2 + 사이드 2)
│   └── items/                        # 아이템 (무기, 방어구, 소모품)
│
├── tests/                            # 테스트 스위트
│   ├── test_rag.py                   # RAG 검색 품질 테스트
│   ├── test_npc.py                   # 페르소나 일관성 테스트
│   ├── test_quest.py                 # 퀘스트 시스템 테스트
│   ├── test_api.py                   # API 통합 테스트
│   ├── test_security.py              # 프롬프트 인젝션 방어 테스트 (30개)
│   └── evaluation_dataset.json       # 50+ Q&A 평가 데이터셋
│
├── scripts/                          # 유틸리티 스크립트
│   ├── demo.py                       # CLI 데모 대화
│   ├── evaluate.py                   # 평가 파이프라인 실행
│   └── ingest.py                     # 세계관 문서 인제스트
│
├── docs/                             # 문서
├── docker-compose.yml                # 4개 서비스 오케스트레이션
├── Dockerfile                        # 멀티스테이지 빌드
└── pyproject.toml                    # Python 패키지 설정
```

---

## 📊 핵심 성과 지표

| 메트릭 | 목표 | 설명 |
|--------|------|------|
| RAG Retrieval Precision | ≥ 0.80 | Top-5 검색 정확도 |
| RAG Retrieval Recall | ≥ 0.70 | Top-5 검색 재현율 |
| 페르소나 일관성 | ≥ 90% | 20턴 연속 대화 기준 |
| 프롬프트 인젝션 방어율 | ≥ 95% | 30개 테스트 패턴 기준 |
| Semantic Cache 히트율 | 측정 중 | LLM 호출 절감 비율 |
| 응답 지연 | 측정 중 | WebSocket 스트리밍 기준 |

---

## 🎮 NPC 소개

### 대장장이 가론 (Blacksmith Garon)
> *"좋은 검은 좋은 쇠에서 나오는 법이지."*
- 52세 · 마스터 대장장이 · 전쟁 참전용사
- 무뚝뚝하지만 속정 깊은 장인
- 관련 퀘스트: 전설의 검 제작, 희귀 광석 수집

### 마녀 엘라라 (Witch Elara)
> *"마법에는 항상 대가가 따르는 법이야."*
- 마법 지식 전문가 · 가론의 오랜 친구
- 신비롭고 도도한 성격

### 상인 리코 (Merchant Rico)
> *"이건 특별히 싸게 드리죠... 단골이시니까."*
- 아이템 거래 · 정보통 · 사교적 성격
- 호감도에 따른 할인 혜택

### 경비대장 테인 (Guard Captain Thane)
> *"이 성벽 안에서 일어나는 일은 내가 다 안다."*
- 세계관 지식 풍부 · 메인 퀘스트 연결
- 정의감 강한 전사

---

## 🔧 기술적 하이라이트

### End-to-End 대화 흐름

```
플레이어: "가론, 전설의 검을 만들 수 있어?"
                    │
    ┌───────────────▼───────────────┐
    │  Security Filter: PASS        │
    │  Intent: quest_inquiry (0.92) │
    │  Sentiment: positive (0.7)    │
    └───────────────┬───────────────┘
                    │
    ┌───────────────▼───────────────┐
    │  RAG: quests/ → main_quest_01 │
    │  "전설의 검 - 고대 용의 강철  │
    │   + 엘프 대장간 불꽃 필요"    │
    └───────────────┬───────────────┘
                    │
    ┌───────────────▼───────────────┐
    │  Emotion: NEUTRAL → EXCITED   │
    │  Affinity: +3 (현재 47/100)   │
    └───────────────┬───────────────┘
                    │
                    ▼
가론: "허! 전설의 검이라... 만들 수 있고말고!
      하지만 재료가 문제지. 고대 용의 강철이
      필요한데, 그건 쉽게 구할 물건이 아니야.
      혹시 서쪽 광산에 대해 들어본 적 있나?"

    [감정: EXCITED 😤] [호감도: 47 → 친구]
    [퀘스트 트리거: main_quest_01 활성화]
```

### 자가 개선 평가 루프

```
┌─────────────────────────────────────────────┐
│           Evaluation Pipeline               │
│                                              │
│  ① Persona Consistency Check                │
│     "NPC가 캐릭터에서 벗어나지 않았는가?"     │
│              │                               │
│  ② Hallucination Detection                  │
│     "세계관에 없는 정보를 생성하지 않았는가?"  │
│              │                               │
│  ③ Response Quality Score                   │
│     "유창성 + 힌트 적절성 + 캐릭터 점수"      │
│              │                               │
│              ▼                               │
│     [평가 결과 → 프롬프트/파이프라인 개선]    │
└─────────────────────────────────────────────┘
```

---

## 🧪 테스트

```bash
# 전체 테스트 실행
pytest tests/ -v

# RAG 품질 테스트
pytest tests/test_rag.py -v

# 보안 테스트 (30개 인젝션 패턴)
pytest tests/test_security.py -v

# 페르소나 일관성 테스트
pytest tests/test_npc.py -v
```

---

## 📐 데이터베이스 스키마

```sql
-- 핵심 테이블 6개
users              -- 플레이어 정보
npcs               -- NPC 기본 정보
user_npc_affinities -- 호감도 + 현재 감정 상태
dialogue_sessions  -- 대화 세션 (요약 포함)
dialogue_messages  -- 개별 메시지 (의도/감성/감정 기록)
quest_progress     -- 퀘스트 진행률 (0-100%)
```

---

## 🗺️ 대시보드 화면 구성

| 화면 | 설명 |
|------|------|
| **Chat Window** | NPC와 실시간 대화, 스트리밍 응답 |
| **NPC Profile** | 현재 감정 상태, 호감도 레벨, 잠금 해제 콘텐츠 |
| **Quest Panel** | 활성 퀘스트 목록, 진행률, 힌트 표시 |
| **World Map** | NPC 위치 시각화, 클릭으로 NPC 선택 |

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
