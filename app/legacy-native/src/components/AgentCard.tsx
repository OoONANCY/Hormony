import React from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import Svg, { Circle, Line, Polyline, Text as SText } from 'react-native-svg';
import { theme } from '../theme';
import { Icon } from './ui';

const AGHEX: Record<string, string> = { lab: theme.lab, symptom: theme.sym, sym: theme.sym, cycle: theme.cyc, cyc: theme.cyc };
const AGNAME: Record<string, string> = { lab: 'Lab Agent', symptom: 'Symptom Agent', cycle: 'Cycle Agent' };

export function AgentCard({ agent, thought, hypothesis, state, evidence, onEvidence }: any) {
  const hex = AGHEX[agent] ?? theme.plum;
  return (
    <View style={[styles.agent, state !== 'queued' && styles.live]}>
      <View style={{ flexDirection: 'row', gap: 12, alignItems: 'center' }}>
        <View style={[styles.av, { backgroundColor: hex }]}><Icon name={agent === 'lab' ? 'flask' : agent.startsWith('sym') ? 'pulse' : 'cycle'} size={22} color="#fff" /></View>
        <View><Text style={styles.aName}>{AGNAME[agent] ?? agent}</Text><Text style={styles.aRole}>{agent === 'lab' ? 'Hormone & lab trends' : agent.startsWith('sym') ? 'Symptom patterns' : 'Cycle-phase timing'}</Text></View>
        <Text style={styles.aState}>{state}</Text>
      </View>
      {(thought ?? []).map((t: string, i: number) => (
        <Text key={i} style={styles.thought}>• {t}</Text>
      ))}
      {hypothesis ? (
        <View style={styles.hyp}>
          <Text style={styles.lbl}>HYPOTHESIS</Text>
          <Text style={styles.claim}>{hypothesis.claim?.replace(/<[^>]+>/g, '')}</Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <View style={styles.bar}><View style={[styles.fill, { width: `${(hypothesis.confidence ?? 0) * 100}%`, backgroundColor: hex }]} /></View>
            <Text>{(hypothesis.confidence ?? 0).toFixed(2)}</Text>
          </View>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
            {(hypothesis.evidence_ids ?? []).map((id: string) => (
              <Pressable key={id} onPress={() => onEvidence?.(id)} style={styles.chip}><Text style={styles.chipText}>{id}</Text></Pressable>
            ))}
          </View>
        </View>
      ) : null}
    </View>
  );
}

export function DiscordanceMap({ discordance }: any) {
  if (!discordance) return null;
  const pairs = discordance.pairs ?? [];
  const conflict = discordance.conflict;
  return (
    <View style={[styles.agent, conflict && styles.disc]}>
      <Text style={styles.discHead}>{conflict ? '⚠ DISCORDANCE DETECTED' : 'PARTIAL AGREEMENT'}</Text>
      <Svg viewBox="0 0 300 190" style={{ width: '100%', height: 150 }}>
        <Circle cx={150} cy={40} r={22} fill={theme.sym} />
        <Circle cx={56} cy={146} r={22} fill={theme.lab} />
        <Circle cx={244} cy={146} r={22} fill={theme.cyc} />
        {pairs.map((p: any, i: number) => (
          <Line key={i} x1={100} y1={80} x2={200} y2={80} stroke={p.relation === 'conflict' ? theme.warn : theme.good} strokeWidth={3} />
        ))}
      </Svg>
      {pairs.map((p: any, i: number) => (
        <Text key={i} style={styles.pair}>{p.a} × {p.b}: {p.relation}</Text>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  agent: { backgroundColor: theme.card, borderRadius: 22, borderWidth: 1, borderColor: theme.line, padding: 18, marginBottom: 14, opacity: 0.95 },
  live: { borderColor: theme.line2 },
  disc: { borderColor: 'rgba(250,178,25,0.55)' },
  av: { width: 44, height: 44, borderRadius: 15, alignItems: 'center', justifyContent: 'center' },
  aName: { fontSize: 15.5, fontWeight: '600', fontFamily: theme.fonts.sans },
  aRole: { fontSize: 12.5, color: theme.muted },
  aState: { marginLeft: 'auto', fontSize: 11, fontWeight: '600', color: theme.faint, textTransform: 'uppercase' },
  thought: { fontSize: 13.5, color: theme.ink2, marginTop: 6 },
  hyp: { marginTop: 14, padding: 14, borderRadius: 16, backgroundColor: theme.card2 },
  lbl: { fontSize: 10.5, letterSpacing: 1.5, color: theme.muted, fontWeight: '600' },
  claim: { fontFamily: theme.fonts.serif, fontSize: 17, marginVertical: 6 },
  bar: { flex: 1, height: 6, borderRadius: 99, backgroundColor: theme.sunk, overflow: 'hidden' },
  fill: { height: '100%', borderRadius: 99 },
  chip: { paddingHorizontal: 9, paddingVertical: 5, borderRadius: 9, backgroundColor: theme.card, borderWidth: 1, borderColor: theme.line2 },
  chipText: { fontSize: 11.5, fontFamily: 'monospace' },
  discHead: { color: '#7a5200', fontWeight: '700', fontSize: 12, letterSpacing: 1.5 },
  pair: { fontSize: 13.5, marginTop: 6 },
});
