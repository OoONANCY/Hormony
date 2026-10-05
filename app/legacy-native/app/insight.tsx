import React, { useEffect, useState } from 'react';
import { ScrollView, View, Text, StyleSheet, Pressable } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { theme } from '../src/theme';
import { Card, Btn } from '../src/components/ui';
import { ConfidenceRing, DotPlot } from '../src/components/Graphs';
import { api } from '../src/api';

export default function Insight() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [why, setWhy] = useState(false);
  useEffect(() => {
    if (id) api.getAnalysis(id as string).then(setData).catch(() => {});
    else api.createAnalysis('Why have my fatigue episodes increased over the last two cycles?', ['lab', 'symptom', 'cycle']).then((r) => api.getAnalysis(r.id).then(setData).catch(() => {})).catch(() => {});
  }, [id]);
  const report = data?.report ?? { headline: 'Your fatigue follows your cycle, and has come more often since Aug 16.', confidence: 0.68 };
  return (
    <ScrollView style={styles.screen} contentContainerStyle={{ paddingBottom: 40 }}>
      <Pressable onPress={() => router.back()} style={styles.back}><Text>‹</Text></Pressable>
      <Text style={styles.eyebrow}>Pattern unlocked · Sep 29</Text>
      <Text style={styles.h3}>Fatigue × cycle × medication</Text>
      <Card>
        <Text style={styles.big}>{report.headline}</Text>
        <ConfidenceRing p={report.confidence ?? 0.68} />
      </Card>
      <Card>
        <Text style={styles.h3}>Fatigue by cycle day</Text>
        <Text style={styles.small}>One row per cycle · dot size = severity</Text>
        <DotPlot fatigue={[{ date: '2026-08-19', severity: 6 }, { date: '2026-09-26', severity: 7 }]} />
      </Card>
      <Btn title={why ? 'Evidence chain shown' : 'Why? Show me the evidence'} onPress={() => setWhy(true)} />
      {why ? (
        <Card>
          {[['Sources', '4 cycles · 10 labs · 26 symptoms · 89 sleep nights'], ['Observations', '13 of 16 fatigue logs on days 20–28; 5 → 11 after Aug 16; P4 7.9 → 4.2'], ['Reasoning', 'Timing repeats every cycle; rise aligns with medication start but sleep also changed.'], ['Confidence', 'Medium: consistent timing, only 2 lab samples.'], ['Alternatives', 'Sleep disruption · Iron/B12 untested · Stress']].map(([h, b], i) => (
            <View key={i} style={{ marginTop: 12 }}><Text style={styles.h3}>{i + 1}. {h}</Text><Text>{b}</Text></View>
          ))}
        </Card>
      ) : null}
      <View style={{ flexDirection: 'row', gap: 10, marginTop: 12 }}>
        <View style={{ flex: 1 }}><Btn title="Graph" kind="ghost" onPress={() => router.push({ pathname: '/graph', params: { id } })} /></View>
        <View style={{ flex: 1 }}><Btn title="Brief" kind="ghost" onPress={() => router.push({ pathname: '/brief', params: { id } })} /></View>
      </View>
    </ScrollView>
  );
}
const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.bg, padding: 18, paddingTop: 58 },
  back: { width: 40, height: 40, borderRadius: 13, backgroundColor: theme.card, borderWidth: 1, borderColor: theme.line, alignItems: 'center', justifyContent: 'center', marginBottom: 12 },
  eyebrow: { fontSize: 11.5, letterSpacing: 1.5, textTransform: 'uppercase', fontWeight: '600', color: theme.muted },
  h3: { fontSize: 15.5, fontWeight: '600' },
  small: { fontSize: 13, color: theme.muted },
  big: { fontFamily: theme.fonts.serif, fontSize: 28, marginVertical: 12 },
});
