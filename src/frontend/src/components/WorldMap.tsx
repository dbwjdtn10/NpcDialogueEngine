import React from 'react';
import { NPCListItem } from '../types';

interface WorldMapProps {
  npcs: NPCListItem[];
  selectedNpcId: string | null;
}

interface Region {
  name: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

const REGIONS: Region[] = [
  { name: '마을 광장', x: 35, y: 20, width: 30, height: 20 },
  { name: '대장간', x: 10, y: 45, width: 20, height: 15 },
  { name: '주점', x: 60, y: 45, width: 25, height: 15 },
  { name: '성벽', x: 5, y: 10, width: 15, height: 15 },
  { name: '시장', x: 35, y: 65, width: 30, height: 15 },
  { name: '숲 입구', x: 75, y: 15, width: 20, height: 15 },
  { name: '신전', x: 10, y: 75, width: 20, height: 15 },
  { name: '도서관', x: 70, y: 70, width: 20, height: 15 },
];

function getNpcRegionPosition(
  location: string,
  index: number
): { x: number; y: number } {
  const region = REGIONS.find((r) =>
    location.toLowerCase().includes(r.name.toLowerCase())
  );

  if (region) {
    return {
      x: region.x + region.width / 2 + (index % 3) * 5 - 5,
      y: region.y + region.height / 2 + Math.floor(index / 3) * 5,
    };
  }

  // Distribute unmatched NPCs across the map
  const angle = (index * 137.5 * Math.PI) / 180;
  return {
    x: 50 + Math.cos(angle) * 25,
    y: 50 + Math.sin(angle) * 20,
  };
}

const WorldMap: React.FC<WorldMapProps> = ({ npcs, selectedNpcId }) => {
  return (
    <div className="world-map">
      <h3 className="panel-title">🗺️ 세계 지도</h3>
      <div className="map-container">
        <svg viewBox="0 0 100 100" className="map-svg">
          {/* Background */}
          <rect width="100" height="100" fill="#0d0d1a" rx="4" />

          {/* Regions */}
          {REGIONS.map((region) => (
            <g key={region.name}>
              <rect
                x={region.x}
                y={region.y}
                width={region.width}
                height={region.height}
                fill="none"
                stroke="#2a2a4a"
                strokeWidth="0.3"
                strokeDasharray="1,1"
                rx="2"
              />
              <text
                x={region.x + region.width / 2}
                y={region.y + 4}
                textAnchor="middle"
                fill="#555580"
                fontSize="2.5"
                fontFamily="sans-serif"
              >
                {region.name}
              </text>
            </g>
          ))}

          {/* NPC dots */}
          {npcs.map((npc, index) => {
            const pos = getNpcRegionPosition(npc.location, index);
            const isSelected = npc.npc_id === selectedNpcId;
            return (
              <g key={npc.npc_id}>
                {isSelected && (
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r="3"
                    fill="none"
                    stroke="#d4a574"
                    strokeWidth="0.3"
                    className="map-selected-ring"
                  />
                )}
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r="1.5"
                  fill={isSelected ? '#d4a574' : '#5b7bb5'}
                  className="map-npc-dot"
                />
                <text
                  x={pos.x}
                  y={pos.y + 4}
                  textAnchor="middle"
                  fill={isSelected ? '#d4a574' : '#8888aa'}
                  fontSize="2"
                  fontFamily="sans-serif"
                >
                  {npc.name}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
};

export default WorldMap;
