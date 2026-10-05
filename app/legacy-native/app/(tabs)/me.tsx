import React, { useEffect, useState } from 'react';
import { ScrollView, View, Text, StyleSheet, Pressable } from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import { theme } from '../../src/theme';
import { Card, Icon } from '../../src/components/ui';
import { useGame, BADGES, levelOf, AgentName } from '../../src/game';
import { api } from '../../src/api';

const AG = [
  { k: 'lab', name: 'Lab Agent', reads: 'Lab results only', hex: theme.lab },
  { k: 'symptom', name: 'Symptom Agent', reads: 'Symptoms + meds', hex: theme.sym },
  { k: 'cycle', name: 'Cycle Agent', reads: 'Cycle + sleep timing', hex: theme.cyc },
];

export default function Me() {
  const { xp, streak, badges, paused, togglePause, earn, addXP } = useGame();
  const L = levelOf(xp);
  const [summary, setSummary] = useState<any>(null);
  useEffect(() => { api.summary('nancy').then(setSummary).catch(() => {}); }, []);
  const importFile = async () => {
    try {
      const f: any = await DocumentPicker.getDocumentAsync({ type: ['text/csv', 'application/json'] });
      if (f.canceled) return;
    } catch {}
  };
  return (
    <ScrollView style={styles.screen} contentContainerStyle={{ paddingBottom: 130 }}>
      <Text style={styles.eyebrow}>Your space</Text>
      <Text style={styles.h1}>You, <Text style={{ fontStyle: 'italic', color: theme.plum }}>in context</Text></Text>
      <Card>
        <Text style={styles.h3}>Nancy</Text>
        <Text style={styles.small}>Level {L.n} · {L.name} · {xp} XP · {streak}-day streak</Text>
        <View style={styles.bar}><View style={[styles.fill, { width: `${Math.min(100, ((xp - L.from) / Math.max(1, (L.to as number) - L.from)) * 100)}%` }]} /></View>
      </Card>
      <Text style={styles.h3}>Badges · {badges.length} of {BADGES.length}</Text>
      <Card>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 12 }}>
          {BADGES.map(([k, _ic, n]) => (
            <View key={k} style={{ width: '22%', alignItems: 'center', opacity: badges.includes(k) ? 1 : 0.4 }}>
              <View style={[styles.badge, !badges.includes(k) && styles.locked]}><Icon name="sparkle" size={20} color={theme.plumDark} /></View>
              <Text style={styles.small}>{n}</Text>
            </View>
          ))}
        </View>
      </Card>
      <Text style={styles.h3}>Agent access</Text>
      <Card>
        {AG.map((a) => (
          <View key={a.k} style={styles.row}>
            <View style={[styles.dot, { backgroundColor: a.hex }]} />
            <View style={{ flex: 1 }}><Text>{a.name}</Text><Text style={styles.small}>{a.reads}</Text></View>
            <Pressable onPress={() => togglePause(a.k as AgentName)} style={[styles.tog, !paused.includes(a.k as AgentName) && { backgroundColor: a.hex }]}>
              <View style={[styles.knob, !paused.includes(a.k as AgentName) && { transform: [{ translateX: 20 }] }]} />
            </Pressable>
          </View>
        ))}
      </Card>
      <Text style={styles.h3}>Data sources</Text>
      <Card>
        {(summary ? Object.entries(summary.counts) : [['lab', 10], ['symptom', 26]]).map(([k, v]: any) => (
          <View key={k} style={styles.row}><Text style={{ flex: 1 }}>{k}</Text><Text>{v} · Synced</Text></View>
        ))}
        <Pressable onPress={importFile} style={styles.import}><Text>Import CSV / JSON</Text></Pressable>
      </Card>
    </ScrollView>
  );
}
const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.bg, padding: 18, paddingTop: 58 },
  eyebrow: { fontSize: 11.5, letterSpacing: 1.5, textTransform: 'uppercase', fontWeight: '600', color: theme.muted },
  h1: { fontFamily: theme.fonts.serif, fontSize: 33, marginBottom: 14 },
  h3: { fontSize: 15.5, fontWeight: '600', marginTop: 16, marginBottom: 8 },
  small: { fontSize: 12.5, color: theme.muted, textAlign: 'center' },
  bar: { height: 8, borderRadius: 99, backgroundColor: theme.sunk, marginTop: 8, overflow: 'hidden' },
  fill: { height: '100%', backgroundColor: theme.plum },
  badge: { width: 54, height: 54, borderRadius: 27, backgroundColor: '#EFE4F5', alignItems: 'center', justifyContent: 'center' },
  locked: { backgroundColor: theme.card2, borderWidth: 1.5, borderStyle: 'dashed', borderColor: theme.line2 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: theme.line },
  dot: { width: 36, height: 36, borderRadius: 12 },
  tog: { width: 48, height: 28, borderRadius: 99, backgroundColor: theme.sunk, padding: 3 },
  knob: { width: 22, height: 22, borderRadius: 11, backgroundColor: '#fff' },
  import: { marginTop: 12, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: theme.line2, alignItems: 'center' },
});
