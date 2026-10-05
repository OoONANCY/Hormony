import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Svg, { Circle } from 'react-native-svg';
import { theme } from '../theme';

export function ConfidenceRing({ p }: { p: number }) {
  const r = 32, c = 2 * Math.PI * r;
  const off = c * (1 - p);
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 14 }}>
      <Svg width={76} height={76} viewBox="0 0 76 76" style={{ transform: [{ rotate: '-90deg' }] }}>
        <Circle cx={38} cy={38} r={r} fill="none" stroke="rgba(30,26,34,0.12)" strokeWidth={8} />
        <Circle cx={38} cy={38} r={r} fill="none" stroke={theme.plum} strokeWidth={8} strokeLinecap="round" strokeDasharray={c.toFixed(1)} strokeDashoffset={off.toFixed(1)} />
      </Svg>
      <View><Text style={{ fontSize: 15.5, fontWeight: '600' }}>{p < 0.55 ? 'Low' : p < 0.7 ? 'Medium' : 'Medium-high'} confidence</Text>
      <Text style={{ fontSize: 13, color: theme.muted }}>A time-based link, not proof of cause.</Text></View>
    </View>
  );
}

export function DotPlot({ fatigue }: { fatigue: any[] }) {
  // 4 rows (cycles), days 20–28 band, dot size = severity. Port of prototype dotplot.
  const W = 320, L = 58, Rr = 8, rowH = 34, T0 = 6, H = T0 + 4 * rowH + 20;
  const cw = (W - L - Rr) / 28;
  const X = (c: number) => L + (c - 0.5) * cw;
  const cycIdx = (date: string) => {
    const starts = ['2026-06-14', '2026-07-12', '2026-08-09', '2026-09-06'];
    let k = 0;
    starts.forEach((s, i) => { if (date >= s) k = i; });
    return k;
  };
  const cd = (date: string) => {
    const starts = ['2026-06-14', '2026-07-12', '2026-08-09', '2026-09-06'];
    let k = 0;
    starts.forEach((s, i) => { if (date >= s) k = i; });
    return Math.round((+new Date(date) - +new Date(starts[k])) / 86400000) + 1;
  };
  return (
    <Svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: H }}>
      {fatigue.map((e: any, i: number) => {
        const cy = T0 + cycIdx(e.date) * rowH + rowH / 2;
        return <Circle key={i} cx={X(cd(e.date))} cy={cy} r={3 + (e.severity ?? 5) * 0.35} fill={theme.sym} stroke="#FFFDF9" strokeWidth={2} />;
      })}
    </Svg>
  );
}

export function HypothesisGraph({ graph, onEdge }: any) {
  if (!graph) return null;
  const nodes = graph.nodes ?? [];
  const edges = graph.edges ?? [];
  // Static settled layout from prototype (physics cut fallback keeps taps).
  const pos: Record<string, [number, number]> = { fat: [177, 200], lut: [80, 95], med: [280, 95], p4: [70, 300], slp: [177, 55], anx: [290, 300], iron: [177, 340] };
  const hex: Record<string, string> = { symptom: theme.sym, cycle: theme.cyc, med: theme.med, lab: theme.lab, sleep: theme.slp, ghost: '#B3ABB6' };
  return (
    <Svg viewBox="0 0 354 400" style={{ width: '100%', height: 380 }}>
      {edges.map((e: any, i: number) => {
        const [x1, y1] = pos[e.a] ?? [177, 200];
        const [x2, y2] = pos[e.b] ?? [177, 200];
        return <React.Fragment key={i}>
          <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="rgba(30,26,34,0.18)" strokeWidth={e.confidence ? 1.5 + e.confidence * 4 : 1.5} strokeDasharray={e.type === 'Untested' ? '4 5' : undefined} />
        </React.Fragment>;
      })}
      {nodes.map((n: any, i: number) => {
        const [x, y] = pos[n.id] ?? [177, 200];
        return <Circle key={i} cx={x} cy={y} r={n.id === 'fat' ? 32 : 22} fill={hex[n.type] ?? theme.plum} stroke="#FFFDF9" strokeWidth={1.5} onPress={() => onEdge?.(n)} />;
      })}
    </Svg>
  );
}
