import React from 'react';
import { QuestStatus } from '../types';

interface QuestPanelProps {
  quests: QuestStatus[];
}

function getStatusLabel(status: string): string {
  switch (status) {
    case 'not_started':
      return '미시작';
    case 'active':
      return '진행 중';
    case 'completed':
      return '완료';
    default:
      return status;
  }
}

function getStatusClass(status: string): string {
  switch (status) {
    case 'not_started':
      return 'quest-not-started';
    case 'active':
      return 'quest-active';
    case 'completed':
      return 'quest-completed';
    default:
      return '';
  }
}

const QuestPanel: React.FC<QuestPanelProps> = ({ quests }) => {
  if (quests.length === 0) {
    return (
      <div className="quest-panel">
        <h3 className="panel-title">퀘스트</h3>
        <div className="quest-empty">
          <p>진행 중인 퀘스트가 없습니다</p>
        </div>
      </div>
    );
  }

  return (
    <div className="quest-panel">
      <h3 className="panel-title">퀘스트</h3>
      <div className="quest-list">
        {quests.map((quest) => (
          <div
            key={quest.quest_id}
            className={`quest-item ${getStatusClass(quest.status)}`}
          >
            <div className="quest-header">
              <span className="quest-name">{quest.title || quest.quest_id}</span>
              <span className={`quest-status-badge ${getStatusClass(quest.status)}`}>
                {getStatusLabel(quest.status)}
              </span>
            </div>

            {quest.status === 'active' && (
              <>
                <div className="quest-progress-container">
                  <div className="quest-progress-bar">
                    <div
                      className="quest-progress-fill"
                      style={{ width: `${quest.progress}%` }}
                    />
                  </div>
                  <span className="quest-progress-text">
                    {quest.progress}%
                  </span>
                </div>

                {quest.current_stage != null && (
                  <div className="quest-stage">
                    현재 단계: {quest.current_stage}
                  </div>
                )}
              </>
            )}

            {quest.related_npcs.length > 0 && (
              <div className="quest-related-npcs">
                관련 NPC: {quest.related_npcs.join(', ')}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default QuestPanel;
