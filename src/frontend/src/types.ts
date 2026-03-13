// Aligned with backend src/api/schemas.py

export interface ChatResponseMetadata {
  intent_confidence: number;
  sentiment: string;
  sentiment_intensity: number;
  rag_sources: string[];
  persona_confidence: number;
  cache_hit: boolean;
  response_time_ms: number;
}

export interface QuestTriggerInfo {
  type: string; // "hint" | "start" | "complete"
  quest_id: string;
  stage: number | null;
  hint_level: string | null;
}

export interface ChatResponse {
  npc_id: string;
  message: string;
  intent: string;
  emotion: string;
  emotion_change: string | null;
  affinity: number;
  affinity_change: number;
  affinity_level: string;
  quest_trigger: QuestTriggerInfo | null;
  metadata: ChatResponseMetadata;
}

export interface NPCProfile {
  npc_id: string;
  name: string;
  occupation: string;
  location: string;
  personality_summary: string;
  current_emotion: string;
  affinity: number;
  affinity_level: string;
  unlocked_features: string[];
}

export interface QuestStatus {
  quest_id: string;
  title: string;
  status: string; // "not_started" | "active" | "completed"
  progress: number; // 0-100
  current_stage: number | null;
  related_npcs: string[];
}

export interface Message {
  id: string;
  sender: 'user' | 'npc';
  npc_name?: string;
  content: string;
  timestamp: Date;
  emotion?: string;
  emotion_change?: string | null;
  intent?: string;
  affinity_change?: number;
  affinity_level?: string;
  quest_trigger?: QuestTriggerInfo | null;
}

export interface NPCListItem {
  npc_id: string;
  name: string;
  location: string;
  current_emotion: string;
}

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';
