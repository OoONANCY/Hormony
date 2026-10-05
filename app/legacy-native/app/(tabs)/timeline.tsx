import React, { useEffect, useState } from 'react';
import { ScrollView, View, Text, StyleSheet, Pressable } from 'react-native';
import { theme, LANE_ORDER } from '../../src/theme';
import { Card } from '../../src/components/ui';
import { LaneChart } from '../../src/components/LaneChart';
import { api } from '../../src/api';
import { useGame } from '../../src/game';

export default function Timeline() {
  const [data, setData] = useState<any>(null);
  const [range, setRange] = useState(90);
  const { completeQuest } = useGame();
  useEffect(() => {
    api.timeline('nancy', range).then(setData).catch(() => {});
    completeQuest('timeline');
  }, [range]);
  const events = data?.events ?? [];
  return (
    <ScrollView style={styles.screen} contentContainerStyle={{ paddingBottom: 130 }}>
      <View style={styles.hdr}><View><Text style={styles.eyebrow}>Jul 1 – Sep 29 · all sources</Text><Text style={styles.h1}>Your <Text style={{ fontStyle: 'italic', color: theme.plum }}>story</Text></Text></View></View>
      <View style={{ flexDirection: 'row', gap: 8, marginBottom: 12 }}>
        {[30, 90].map((r) => (
          <Pressable key={r} onPress={() => setRange(r)} style={[styles.seg, range === r && styles.segOn]}><Text>{r} days</Text></Pressable>
        ))}
      </View>
      <Card>
        <LaneChart events={events} days={range} />
      </Card>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginVertical: 10 }}>
        <Text style={styles.h3}>Hormone trends</Text>
      </View>
      <Card>
        {['E2', 'P4', 'TSH'].map((code) => {
          const pts = events.filter((e: any) => e.code === code);
          if (!pts.length) return null;
          const last = pts[pts.length - 1];
          return <View key={code} style={{ marginTop: 12 }}><Text style={styles.h3}>{code}</Text><Text style={{ fontSize: 20 }}>{last.value} <Text style={{ fontSize: 12, color: theme.muted }}>{last.unit}</Text></Text></View>;
        })}
      </Card>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginVertical: 10 }}>
        <Text style={styles.h3}>Evidence ledger</Text><Text style={styles.small}>{events.length} records</Text>
      </View>
      <Card>
        {events.slice(-15).reverse().map((e: any) => (
          <View key={e.id} style={styles.feed}><Text style={{ fontWeight: '500' }}>{e.name} {e.value ?? ''}{e.unit ?? ''}{e.severity ? ` ${e.severity}/10` : ''}</Text><Text style={styles.small}>{e.date} · day {e.cycle_day} · {e.source}</Text></View>
        ))}
      </Card>
    </ScrollView>
  );
}
const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.bg, padding: 18, paddingTop: 58 },
  hdr: { marginBottom: 18 },
  eyebrow: { fontSize: 11.5, letterSpacing: 1.5, textTransform: 'uppercase', fontWeight: '600', color: theme.muted },
  h1: { fontFamily: theme.fonts.serif, fontSize: 33 },
  h3: { fontSize: 15.5, fontWeight: '600' },
  small: { fontSize: 13, color: theme.muted },
  seg: { paddingHorizontal: 12, height: 30, borderRadius: 9, backgroundColor: theme.sunk, justifyContent: 'center' },
  segOn: { backgroundColor: theme.card },
  feed: { paddingVertical: 11, borderBottomWidth: 1, borderBottomColor: theme.line },
});
