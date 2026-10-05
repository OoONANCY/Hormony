// Gamification store — LEVELS, BADGES, QUEST ported verbatim from prototype.
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';

export type AgentName = 'lab' | 'symptom' | 'cycle';
export const LEVELS: [number, string, number][] = [
  [1, 'Curious', 0],
  [2, 'Noticer', 200],
  [3, 'Pattern Seeker', 350],
  [4, 'Signal Sleuth', 500],
  [5, 'Rhythm Reader', 800],
];
export const BADGES: [string, string, string][] = [
  ['first', 'leaf', 'First log'],
  ['streak7', 'flame', '7-day streak'],
  ['lab', 'flask', 'Lab uploader'],
  ['pattern', 'unlock', 'Pattern unlocked'],
  ['debate', 'scale', 'First debate'],
  ['quest', 'target', 'Quest complete'],
  ['scan', 'scan', 'Report scanner'],
  ['brief', 'doc', 'Clinician-ready'],
  ['exp', 'dna', 'Experimenter'],
  ['sleuth', 'search', 'Signal Sleuth'],
  ['streak30', 'moon', '30-day streak'],
  ['three', 'star', '3 insights'],
];
export type QuestKey = 'checkin' | 'timeline' | 'ask';

export function levelOf(xp: number) {
  let L = LEVELS[0];
  for (const l of LEVELS) if (xp >= l[2]) L = l;
  const nx = LEVELS.find((l) => l[2] > xp);
  return { n: L[0], name: L[1], from: L[2], to: nx ? nx[2] : L[2], next: nx as any };
}

interface GameState {
  xp: number;
  streak: number;
  evidence: number;
  unlocked: boolean;
  quest: Record<QuestKey, boolean>;
  badges: string[];
  paused: AgentName[];
  addXP: (n: number) => boolean;
  earn: (b: string) => void;
  completeQuest: (k: QuestKey) => void;
  togglePause: (a: AgentName) => void;
  bumpEvidence: (n: number) => void;
  unlock: () => void;
}

export const useGame = create<GameState>()(
  persist(
    (set, get) => ({
      xp: 410,
      streak: 12,
      evidence: 80,
      unlocked: false,
      quest: { checkin: false, timeline: false, ask: false },
      badges: ['first', 'streak7', 'lab'],
      paused: [] as AgentName[],
      addXP: (n) => {
        const before = levelOf(get().xp);
        set({ xp: get().xp + n });
        return levelOf(get().xp).n > before.n;
      },
      earn: (b) => {
        if (get().badges.includes(b)) return;
        set({ badges: [...get().badges, b] });
      },
      completeQuest: (k) => set({ quest: { ...get().quest, [k]: true } }),
      togglePause: (a) =>
        set({ paused: get().paused.includes(a) ? get().paused.filter((x) => x !== a) : [...get().paused, a] }),
      bumpEvidence: (n) => set({ evidence: Math.min(100, get().evidence + n) }),
      unlock: () => set({ unlocked: true, evidence: 100 }),
    }),
    { name: 'hormony-game', storage: createJSONStorage(() => AsyncStorage) }
  )
);
