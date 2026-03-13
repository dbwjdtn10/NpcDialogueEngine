# README 포함 내용 (포트폴리오 어필용)

## 프로젝트 동기
게임 NPC 대화의 한계(반복적, 고정 스크립트)를 LLM + RAG로 해결.
세계관 충실성을 유지하면서 동적이고 개인화된 NPC 대화 경험을 제공합니다.

## 주요 성과
- RAG Faithfulness Score: 0.XX
- RAG Retrieval Precision: 0.XX (Top-5 기준)
- 페르소나 일관성: 20턴 연속 대화에서 XX% 유지
- 할루시네이션율: X% 미만
- 프롬프트 인젝션 방어율: XX% (30개 테스트셋)
- WebSocket 기반 실시간 대화 (평균 응답 XXms)
- Semantic Cache 히트율: XX% (LLM 호출 절감)
- NPC 4종 x 감정 6종 x 호감도 5단계 = 동적 응답 시스템

## 실행 방법
```bash
docker-compose up --build
# API: http://localhost:8000/docs
# Chat UI: http://localhost:5173
# CLI 데모: python scripts/demo.py --npc garon
```
