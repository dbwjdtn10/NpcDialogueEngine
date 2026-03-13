import React from 'react';
import { NPCProfile as NPCProfileType } from '../types';

interface NPCProfileProps {
  profile: NPCProfileType | null;
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

// Matches backend affinity.py AFFINITY_LEVELS: (0,20), (21,40), (41,60), (61,80), (81,100)
function getAffinityColor(affinity: number): string {
  if (affinity <= 20) return '#888';
  if (affinity <= 40) return '#5b9bd5';
  if (affinity <= 60) return '#70ad47';
  if (affinity <= 80) return '#d4a574';
  return '#ffd700';
}

function getAvatarColor(name: string): string {
  const colors = [
    '#e74c3c', '#3498db', '#2ecc71', '#9b59b6',
    '#e67e22', '#1abc9c', '#f39c12', '#c0392b',
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

const NPCProfile: React.FC<NPCProfileProps> = ({ profile }) => {
  if (!profile) {
    return (
      <div className="npc-profile">
        <div className="npc-profile-empty">
          <p>NPC를 선택하세요</p>
        </div>
      </div>
    );
  }

  const affinityColor = getAffinityColor(profile.affinity);
  const emotionIcon = EMOTION_ICONS[profile.current_emotion.toLowerCase()] || '😐';

  return (
    <div className="npc-profile">
      <div className="npc-profile-header">
        <div
          className="npc-avatar"
          style={{ backgroundColor: getAvatarColor(profile.name) }}
        >
          {profile.name.charAt(0)}
        </div>
        <div className="npc-basic-info">
          <h3 className="npc-name">{profile.name}</h3>
          {profile.occupation && (
            <span className="npc-occupation">{profile.occupation}</span>
          )}
          <span className="npc-location">{profile.location}</span>
        </div>
      </div>

      <div className="npc-emotion-section">
        <span className="section-label">현재 감정</span>
        <span className={`emotion-badge emotion-${profile.current_emotion.toLowerCase()}`}>
          {emotionIcon} {profile.current_emotion}
        </span>
      </div>

      <div className="npc-affinity-section">
        <div className="affinity-header">
          <span className="section-label">호감도</span>
          <span className="affinity-level" style={{ color: affinityColor }}>
            {profile.affinity_level}
          </span>
        </div>
        <div className="affinity-bar-container">
          <div
            className="affinity-bar"
            style={{
              width: `${profile.affinity}%`,
              background: `linear-gradient(90deg, ${affinityColor}88, ${affinityColor})`,
            }}
          />
          <span className="affinity-value">{profile.affinity}</span>
        </div>
      </div>

      {profile.personality_summary && (
        <div className="npc-detail-section">
          <span className="section-label">성격</span>
          <p className="npc-personality">{profile.personality_summary}</p>
        </div>
      )}

      {profile.unlocked_features.length > 0 && (
        <div className="npc-detail-section">
          <span className="section-label">해금된 기능</span>
          <div className="knowledge-tags">
            {profile.unlocked_features.map((feature) => (
              <span key={feature} className="knowledge-tag">
                {feature}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default NPCProfile;
