// CycleRing — port of renderRing() geometry (arc, dayA, pt) to react-native-svg.
// 28 segments, phase opacities, inner tracks, today marker.
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Svg, { Path, Circle, Text as SText, TextPath, Defs, Filter, FeGaussianBlur, FeMerge, FeMergeNode } from 'react-native-svg';
import { theme } from '../theme';

const RC = 150, R_SEG = 118, SEG = 360 / 28;
const dayA = (c: number) => -90 + (c - 1) * SEG;
const pt = (r: number, a: number): [number, number] => {
  const t = (a * Math.PI) / 180;
  return [RC + r * Math.cos(t), RC + r * Math.sin(t)];
};
function arc(r: number, a0: number, a1: number, rev = false) {
  const [x0, y0] = pt(r, a0), [x1, y1] = pt(r, a1);
  const l = a1 - a0 > 180 ? 1 : 0;
  return rev
    ? `M${x1.toFixed(2)} ${y1.toFixed(2)}A${r} ${r} 0 ${l} 0 ${x0.toFixed(2)} ${y0.toFixed(2)}`
    : `M${x0.toFixed(2)} ${y0.toFixed(2)}A${r} ${r} 0 ${l} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
}
const segStyle = (c: number): [string, number] =>
  c <= 5 ? ['#9a6bc0', 1] : c <= 13 ? ['#9a6bc0', 0.24] : c <= 16 ? ['#9a6bc0', 0.72] : c <= 19 ? ['#9a6bc0', 0.4] : ['#9a6bc0', 0.58];

// cycle maths ported from prototype
export function cdOf(dateStr: string, starts: string[]): number | null {
  const d = new Date(dateStr + 'T00:00:00');
  const ss = starts.map((s) => new Date(s + 'T00:00:00')).filter((s) => s <= d).sort((a, b) => +a - +b);
  if (!ss.length) return null;
  return Math.round((+d - +ss[ss.length - 1]) / 86400000) + 1;
}
export function phaseOf(c: number) {
  if (c <= 5) return 'Period';
  if (c <= 13) return 'Follicular';
  if (c <= 16) return 'Ovulation';
  if (c <= 19) return 'Early luteal';
  return 'Late luteal';
}

export function CycleRing({ cycleDay, events, starts }: { cycleDay: number; events: any[]; starts: string[] }) {
  const tc = cycleDay;
  const segs = [];
  for (let c = 1; c <= 28; c++) {
    const [col, op] = segStyle(c);
    const fut = c > tc;
    segs.push(
      <Path key={c} d={arc(R_SEG, dayA(c) + 0.9, dayA(c + 1) - 0.9)} stroke={col} strokeOpacity={fut ? op * 0.35 : op} strokeWidth={c === tc ? 24 : 18} fill="none" />
    );
  }
  const [tx, ty] = pt(R_SEG, dayA(tc) + SEG / 2);
  return (
    <View style={styles.wrap}>
      <Svg viewBox="0 0 300 300" style={{ width: '100%', aspectRatio: 1 }}>
        {[94, 82, 70].map((r) => (
          <Circle key={r} cx={RC} cy={RC} r={r} fill="none" stroke="rgba(30,26,34,0.06)" />
        ))}
        {segs}
        <Circle cx={tx} cy={ty} r={14} fill="#E9D9F5" opacity={0.85} />
        <Circle cx={tx} cy={ty} r={6.5} fill="#fff" stroke={theme.plum} strokeWidth={2.5} />
      </Svg>
      <View style={styles.center} pointerEvents="none">
        <Text style={styles.eyebrow}>Cycle day</Text>
        <Text style={styles.day}>{tc}</Text>
        <Text style={styles.phase}>{phaseOf(tc)}</Text>
      </View>
    </View>
  );
}
const styles = StyleSheet.create({
  wrap: { position: 'relative', width: 300, maxWidth: '100%', alignSelf: 'center' },
  center: { position: 'absolute', inset: 0, alignItems: 'center', justifyContent: 'center' },
  eyebrow: { fontSize: 10.5, letterSpacing: 1.5, textTransform: 'uppercase', color: theme.muted, fontWeight: '600', fontFamily: theme.fonts.sans },
  day: { fontSize: 58, fontWeight: '300', letterSpacing: -2, fontFamily: theme.fonts.sans },
  phase: { fontFamily: theme.fonts.serif, fontStyle: 'italic', fontSize: 18, color: theme.plum },
});
