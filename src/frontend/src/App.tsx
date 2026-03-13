import React, { useCallback, useEffect, useState } from 'react';
import ChatWindow from './components/ChatWindow';
import NPCProfile from './components/NPCProfile';
import QuestPanel from './components/QuestPanel';
import WorldMap from './components/WorldMap';
import { useWebSocket } from './hooks/useWebSocket';
import {
  ChatResponse,
  Message,
  NPCListItem,
  NPCProfile as NPCProfileType,
  QuestStatus,
} from './types';

const USER_ID = 'player_001';

// Demo NPC data matching backend worldbuilding NPC IDs
const DEMO_NPCS: NPCListItem[] = [
  { npc_id: 'blacksmith_garon', name: '대장장이 가론', location: '대장간', current_emotion: 'neutral' },
  { npc_id: 'witch_elara', name: '마녀 엘라라', location: '마법의 탑', current_emotion: 'neutral' },
  { npc_id: 'merchant_rico', name: '상인 리코', location: '시장', current_emotion: 'neutral' },
  { npc_id: 'guard_captain_thane', name: '경비대장 세인', location: '성문', current_emotion: 'neutral' },
];

function generateMessageId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

const App: React.FC = () => {
  const [npcList, setNpcList] = useState<NPCListItem[]>(DEMO_NPCS);
  const [selectedNpcId, setSelectedNpcId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [npcProfile, setNpcProfile] = useState<NPCProfileType | null>(null);
  const [quests, setQuests] = useState<QuestStatus[]>([]);

  const selectedNpc = npcList.find((n) => n.npc_id === selectedNpcId) || null;

  const handleNpcResponse = useCallback(
    (response: ChatResponse) => {
      const npcMsg: Message = {
        id: generateMessageId(),
        sender: 'npc',
        npc_name: selectedNpc?.name,
        content: response.message,
        timestamp: new Date(),
        emotion: response.emotion,
        emotion_change: response.emotion_change,
        intent: response.intent,
        affinity_change: response.affinity_change,
        affinity_level: response.affinity_level,
        quest_trigger: response.quest_trigger,
      };
      setMessages((prev) => [...prev, npcMsg]);

      // Update profile affinity and emotion
      if (npcProfile) {
        setNpcProfile((prev) =>
          prev
            ? {
                ...prev,
                affinity: response.affinity,
                current_emotion: response.emotion,
                affinity_level: response.affinity_level,
              }
            : prev
        );
      }

      // Update NPC list emotion
      setNpcList((prev) =>
        prev.map((npc) =>
          npc.npc_id === response.npc_id
            ? { ...npc, current_emotion: response.emotion }
            : npc
        )
      );

      // Handle quest triggers
      if (response.quest_trigger) {
        const trigger = response.quest_trigger;
        setQuests((prev) => {
          const existing = prev.find((q) => q.quest_id === trigger.quest_id);
          if (existing) {
            return prev.map((q) =>
              q.quest_id === trigger.quest_id
                ? {
                    ...q,
                    status:
                      trigger.type === 'complete'
                        ? 'completed'
                        : trigger.type === 'start'
                          ? 'active'
                          : q.status,
                    current_stage: trigger.stage ?? q.current_stage,
                  }
                : q
            );
          } else {
            return [
              ...prev,
              {
                quest_id: trigger.quest_id,
                title: trigger.quest_id,
                status: trigger.type === 'start' ? 'active' : 'not_started',
                progress: 0,
                current_stage: trigger.stage,
                related_npcs: [],
              },
            ];
          }
        });
      }
    },
    [selectedNpc, npcProfile]
  );

  const { connect, disconnect, sendMessage, status, isNpcTyping } =
    useWebSocket({
      onMessage: handleNpcResponse,
    });

  const handleSelectNpc = useCallback(
    (npcId: string) => {
      if (npcId === selectedNpcId) return;

      disconnect();
      setMessages([]);
      setSelectedNpcId(npcId);

      const npc = npcList.find((n) => n.npc_id === npcId);
      if (npc) {
        // Set a default profile - in production, fetch from API
        setNpcProfile({
          npc_id: npc.npc_id,
          name: npc.name,
          occupation: '',
          location: npc.location,
          personality_summary: '',
          current_emotion: npc.current_emotion,
          affinity: 15,
          affinity_level: '낯선 사람',
          unlocked_features: [],
        });
      }

      connect(npcId, USER_ID);
    },
    [selectedNpcId, npcList, connect, disconnect]
  );

  const handleSendMessage = useCallback(
    (content: string) => {
      const userMsg: Message = {
        id: generateMessageId(),
        sender: 'user',
        content,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMsg]);
      sendMessage(content);
    },
    [sendMessage]
  );

  // Try to fetch NPC list from API on mount
  useEffect(() => {
    fetch('/api/v1/npcs')
      .then((res) => {
        if (res.ok) return res.json();
        throw new Error('API not available');
      })
      .then((data: NPCListItem[]) => {
        if (data && data.length > 0) {
          setNpcList(data);
        }
      })
      .catch(() => {
        // Use demo data silently
      });
  }, []);

  // Fetch quests when NPC selected
  useEffect(() => {
    if (!selectedNpcId) return;
    fetch('/api/v1/quests')
      .then((res) => {
        if (res.ok) return res.json();
        throw new Error('API not available');
      })
      .then((data: QuestStatus[]) => {
        if (data) setQuests(data);
      })
      .catch(() => {
        // Keep existing quests
      });
  }, [selectedNpcId]);

  // Fetch profile when NPC selected
  useEffect(() => {
    if (!selectedNpcId) return;
    fetch(`/api/v1/npcs/${selectedNpcId}/profile`)
      .then((res) => {
        if (res.ok) return res.json();
        throw new Error('API not available');
      })
      .then((data: NPCProfileType) => {
        if (data) setNpcProfile(data);
      })
      .catch(() => {
        // Keep default profile
      });
  }, [selectedNpcId]);

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">NPC 대화 엔진</h1>
        <span className="app-subtitle">NPC Dialogue Engine</span>
      </header>

      <main className="app-layout">
        {/* Left Sidebar - NPC List */}
        <aside className="sidebar sidebar-left">
          <h2 className="sidebar-title">NPC 목록</h2>
          <ul className="npc-list">
            {npcList.map((npc) => (
              <li
                key={npc.npc_id}
                className={`npc-list-item ${
                  npc.npc_id === selectedNpcId ? 'npc-list-item-active' : ''
                }`}
                onClick={() => handleSelectNpc(npc.npc_id)}
              >
                <div
                  className="npc-list-avatar"
                  style={{
                    backgroundColor:
                      npc.npc_id === selectedNpcId ? '#d4a574' : '#2a2a4a',
                  }}
                >
                  {npc.name.charAt(0)}
                </div>
                <div className="npc-list-info">
                  <span className="npc-list-name">{npc.name}</span>
                  <span className="npc-list-location">{npc.location}</span>
                </div>
                <span
                  className={`emotion-dot emotion-${npc.current_emotion.toLowerCase()}`}
                  title={npc.current_emotion}
                />
              </li>
            ))}
          </ul>

          <WorldMap npcs={npcList} selectedNpcId={selectedNpcId} />
        </aside>

        {/* Center - Chat */}
        <ChatWindow
          messages={messages}
          npcName={selectedNpc?.name || null}
          npcEmotion={npcProfile?.current_emotion || null}
          connectionStatus={status}
          isNpcTyping={isNpcTyping}
          onSendMessage={handleSendMessage}
        />

        {/* Right Sidebar - Profile & Quests */}
        <aside className="sidebar sidebar-right">
          <NPCProfile profile={npcProfile} />
          <QuestPanel quests={quests} />
        </aside>
      </main>
    </div>
  );
};

export default App;
