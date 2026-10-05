// LaneChart — port of renderLanes() into RN ScrollView + SVG.
import React from 'react';
import { ScrollView, View, Text, StyleSheet, Pressable } from 'react-native';
import Svg, { Rect, Circle, Line, Text as SText } from 'react-native-svg';
import { theme, LANE_ORDER } from '../theme';

const LANE_H: Record<string, number> = { cyc: 30, lab: 38, sym: 48, slp: 48, med: 32 };

export function LaneChart({ events, days = 90, onSelectDay, selected }: any) {
  const today = '2026-09-29';
  const all = [...events].sort((a, b) => (a.date < b.date ? -1 : 1));
  const dates = all.map((e) => e.date);
  const minDate = days === 90 ? '2026-07-01' : '2026-08-31';
  const vis = all.filter((e) => e.date >= minDate);
  const n = 90;
  const W = Math.max(320, n * 9);
  const dw = 9;
  const x = (date: string) => {
    const d = Math.round((+new Date(date) - +new Date(minDate)) / 86400000);
    return 6 + (d + 0.5) * dw;
  };
  let y = 22;
  const rows: Record<string, any> = {};
  for (const k of LANE_ORDER) { rows[k] = { y, h: LANE_H[k] }; y += LANE_H[k]; }
  const H = y + 22;
  return (
    <View>
      <View style={{ flexDirection: 'row' }}>
        <View style={{ width: 38 }}>
          {LANE_ORDER.map((k) => (
            <View key={k} style={{ position: 'absolute', top: rows[k].y + rows[k].h / 2 - 13 }}>
              <View style={{ width: 26, height: 26, borderRadius: 9, backgroundColor: ({ cyc: theme.cyc, lab: theme.lab, sym: theme.sym, slp: theme.slp, med: theme.med } as any)[k], alignItems: 'center', justifyContent: 'center' }}>
                <Text style={{ color: '#fff', fontSize: 10 }}>{k[0].toUpperCase()}</Text>
              </View>
            </View>
          ))}
        </View>
        <ScrollView horizontal style={{ flex: 1 }}>
          <Pressable onPress={(e: any) => {}}>
            <Svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
              {LANE_ORDER.map((k, i) => (
                <Line key={k} x1={0} x2={W} y1={rows[k].y} y2={rows[k].y} stroke="rgba(30,26,34,0.06)" />
              ))}
              {vis.filter((e) => e.type === 'lab').map((e: any, i: number) => (
                <Circle key={e.id + i} cx={x(e.date)} cy={rows.lab.y + rows.lab.h / 2 - 5} r={5.5} fill={theme.lab} stroke="#FFFDF9" strokeWidth={2} />
              ))}
              {vis.filter((e) => e.type === 'symptom' || e.type === 'sym').map((e: any, i: number) => (
                <Circle key={e.id + i} cx={x(e.date)} cy={rows.sym.y + 12} r={3 + (e.severity ?? 5) * 0.28} fill={theme.sym} stroke="#FFFDF9" strokeWidth={2} />
              ))}
              {vis.filter((e) => e.type === 'sleep' || e.type === 'slp').map((e: any, i: number) => {
                const h = e.value ?? 7;
                const bh = Math.max(2, (Math.min(9, h) - 4) * 3);
                return <Rect key={e.id + i} x={x(e.date) - 3} y={rows.slp.y + rows.slp.h - 6 - bh} width={6} height={bh} fill={theme.slp} opacity={h < 6.5 ? 1 : 0.4} rx={2} />;
              })}
              <Line x1={x(today)} x2={x(today)} y1={18} y2={y} stroke="rgba(30,26,34,0.5)" strokeWidth={1.5} />
              <SText x={x(today) + 5} y={H - 6} fontSize={10.5} fill={theme.muted}>Today</SText>
            </Svg>
          </Pressable>
        </ScrollView>
      </View>
    </View>
  );
}
