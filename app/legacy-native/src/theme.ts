// Design tokens copied verbatim from hormony-app.html :root.
// Pixel-perfect target: bg #F6F2EC, card #FFFDF9, ink #1E1A22, plum #5A3D6E.
export const theme = {
  bg: '#F6F2EC',
  card: '#FFFDF9',
  card2: '#F3EEE6',
  sunk: '#ECE6DC',
  line: 'rgba(30,26,34,0.08)',
  line2: 'rgba(30,26,34,0.15)',
  ink: '#1E1A22',
  ink2: '#4B4452',
  muted: '#7D7584',
  faint: '#A8A0AC',
  plum: '#5A3D6E',
  plumDark: '#452E56',
  plumWash: '#EFE8F2',
  cyc: '#9a6bc0',
  lab: '#16917f',
  sym: '#c4614f',
  slp: '#4f79b8',
  med: '#b08433',
  warn: '#fab219',
  good: '#0ca30c',
  pearl: ['#f2c9e2', '#cdbff5', '#b6dcf2', '#bfead6', '#f2e1b6', '#f1c3cf'] as string[],
  pearlDeep: ['#d98fbf', '#a592e6', '#7fbde2', '#8fd1b3', '#dcbb78', '#dc93a6'] as string[],
  fonts: { serif: 'Newsreader', sans: 'Inter' },
  radius: { card: 22, btn: 14, pill: 99 },
  iconSize: 20,
  iconStroke: 1.6,
} as const;

export type DataLane = 'cyc' | 'lab' | 'sym' | 'slp' | 'med';
export const LANE_ORDER: DataLane[] = ['cyc', 'lab', 'sym', 'slp', 'med'];
export const LANE_META: Record<DataLane, { name: string; hex: string }> = {
  cyc: { name: 'Cycle', hex: theme.cyc },
  lab: { name: 'Labs', hex: theme.lab },
  sym: { name: 'Symptoms', hex: theme.sym },
  slp: { name: 'Sleep', hex: theme.slp },
  med: { name: 'Meds', hex: theme.med },
};
