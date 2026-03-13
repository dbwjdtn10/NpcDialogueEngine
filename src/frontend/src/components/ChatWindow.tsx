import React, { useEffect, useRef, useState } from 'react';
import { Message, ConnectionStatus } from '../types';

interface ChatWindowProps {
  messages: Message[];
  npcName: string | null;
  npcEmotion: string | null;
  connectionStatus: ConnectionStatus;
  isNpcTyping: boolean;
  onSendMessage: (content: string) => void;
}

const EMOTION_ICONS: Record<string, string> = {
  happy: '😊',
  angry: '😠',
  sad: '😢',
  fearful: '😨',
  surprised: '😲',
  neutral: '😐',
  curious: '🤔',
  disgusted: '🤢',
  excited: '🤩',
  grateful: '🙏',
  suspicious: '🧐',
  friendly: '😄',
};

function getEmotionIcon(emotion: string): string {
  return EMOTION_ICONS[emotion.toLowerCase()] || '😐';
}

function formatTimestamp(date: Date): string {
  return date.toLocaleTimeString('ko-KR', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

const ChatWindow: React.FC<ChatWindowProps> = ({
  messages,
  npcName,
  npcEmotion,
  connectionStatus,
  isNpcTyping,
  onSendMessage,
}) => {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isNpcTyping]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) return;
    onSendMessage(trimmed);
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  if (!npcName) {
    return (
      <div className="chat-window">
        <div className="chat-empty">
          <div className="chat-empty-icon">💬</div>
          <p>NPC를 선택하여 대화를 시작하세요</p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-window">
      <div className="chat-header">
        <div className="chat-header-info">
          <span className="chat-header-name">{npcName}</span>
          {npcEmotion && (
            <span className="chat-header-emotion">
              {getEmotionIcon(npcEmotion)} {npcEmotion}
            </span>
          )}
        </div>
        <div className={`connection-status connection-${connectionStatus}`}>
          <span className="connection-dot" />
          {connectionStatus === 'connected'
            ? '연결됨'
            : connectionStatus === 'connecting'
              ? '연결 중...'
              : connectionStatus === 'error'
                ? '오류'
                : '연결 끊김'}
        </div>
      </div>

      <div className="chat-messages" ref={chatContainerRef}>
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`chat-message chat-message-${msg.sender}`}
          >
            <div className="message-bubble">
              <div className="message-sender">
                {msg.sender === 'npc' ? msg.npc_name || npcName : '나'}
              </div>
              <div className="message-content">{msg.content}</div>
              <div className="message-footer">
                <span className="message-time">
                  {formatTimestamp(msg.timestamp)}
                </span>
                {msg.sender === 'npc' && msg.intent && (
                  <span className="message-meta">
                    의도: {msg.intent}
                  </span>
                )}
                {msg.sender === 'npc' &&
                  msg.affinity_change !== undefined &&
                  msg.affinity_change !== 0 && (
                    <span
                      className={`message-meta affinity-change ${
                        msg.affinity_change > 0
                          ? 'affinity-positive'
                          : 'affinity-negative'
                      }`}
                    >
                      호감도 {msg.affinity_change > 0 ? '+' : ''}
                      {msg.affinity_change}
                    </span>
                  )}
              </div>
              {msg.quest_trigger && (
                <div className="message-quest-trigger">
                  퀘스트: {msg.quest_trigger.quest_id} (
                  {msg.quest_trigger.type === 'start'
                    ? '시작'
                    : msg.quest_trigger.type === 'hint'
                      ? '힌트'
                      : '완료'}
                  )
                </div>
              )}
            </div>
          </div>
        ))}

        {isNpcTyping && (
          <div className="chat-message chat-message-npc">
            <div className="message-bubble typing-indicator">
              <span className="typing-dot" />
              <span className="typing-dot" />
              <span className="typing-dot" />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <form className="chat-input-area" onSubmit={handleSubmit}>
        <input
          type="text"
          className="chat-input"
          placeholder="메시지를 입력하세요..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={connectionStatus !== 'connected'}
        />
        <button
          type="submit"
          className="chat-send-btn"
          disabled={connectionStatus !== 'connected' || !input.trim()}
        >
          전송
        </button>
      </form>
    </div>
  );
};

export default ChatWindow;
