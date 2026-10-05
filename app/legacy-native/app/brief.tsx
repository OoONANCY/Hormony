import React, { useEffect, useState } from 'react';
import { ScrollView, View, Text, StyleSheet, Pressable, Share } from 'react-native';
import * as Clipboard from 'expo-clipboard';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { theme } from '../src/theme';
import { Btn } from '../src/components/ui';
import { api } from '../src/api';
import { useGame } from '../src/game';

export default function Brief() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [qs, setQs] = useState<number[]>([0, 1, 2]);
  const { earn, addXP } = useGame();
  useEffect(() => { if (id) api.getAnalysis(id as string).then(setData).catch(() => {}); }, [id]);
  const brief = data?.brief ?? { observed: ['Fatigue clusters on days 20–28', 'P4 7.9 → 4.2; TSH stable', 'Fatigue rose after Aug 16', 'Sleep fell on comparable nights'], interpretation: 'Multiple factors may explain the pattern; no single cause established.', questions: ['Could cycle timing be relevant?', 'Should P4 be evaluated with symptoms?', 'Could spironolactone contribute?', 'Would iron/B12 testing help?'], footer: 'Not a diagnosis.', text: 'Endocrine Insight Report' };
  const copy = async () => { await Clipboard.setStringAsync(brief.text ?? ''); earn('brief'); addXP(20); };
  const share = async () => { try { await Share.share({ message: brief.text ?? '' }); } catch {} };
  const QUESTIONS = brief.questions ?? [];
  return (
    <ScrollView style={styles.screen} contentContainerStyle={{ paddingBottom: 40 }}>
      <Pressable onPress={() => router.back()} style={styles.back}><Text>‹</Text></Pressable>
      <Text style={styles.eyebrow}>Ready for your appointment</Text>
      <Text style={styles.h2}>Clinician <Text style={{ fontStyle: 'italic', color: theme.plum }}>brief</Text></Text>
      <View style={styles.paper}>
        <Text style={styles.pt}>Endocrine Insight Report</Text>
        <Text style={styles.small}>Nancy · Jul 1 – Sep 29, 2026 (91 days)</Text>
        <Text style={styles.h5}>OBSERVED PATTERNS</Text>
        {(brief.observed ?? []).map((o: string, i: number) => (
          <View key={i} style={styles.obs}><View style={[styles.n, { backgroundColor: [theme.sym, theme.lab, theme.med, theme.slp][i % 4] }]}><Text style={{ color: '#fff', fontWeight: '700' }}>{i + 1}</Text></View><Text style={{ flex: 1 }}>{o}</Text></View>
        ))}
        <Text style={styles.h5}>SYSTEM INTERPRETATION</Text>
        <Text style={styles.interp}>{brief.interpretation}</Text>
        <Text style={styles.h5}>QUESTIONS FOR MY CLINICIAN</Text>
        {QUESTIONS.map((qq: string, i: number) => (
          <Pressable key={i} onPress={() => setQs(qs.includes(i) ? qs.filter((x) => x !== i) : [...qs, i])} style={{ flexDirection: 'row', gap: 10, paddingVertical: 8, opacity: qs.includes(i) ? 1 : 0.4 }}>
            <View style={[styles.box, qs.includes(i) && { backgroundColor: theme.plum }]}><Text style={{ color: '#fff' }}>✓</Text></View><Text style={{ flex: 1 }}>{qq}</Text>
          </Pressable>
        ))}
        <Text style={styles.foot}>{brief.footer}</Text>
      </View>
      <View style={{ flexDirection: 'row', gap: 10, marginTop: 16 }}>
        <View style={{ flex: 1 }}><Btn title="Copy" kind="ghost" onPress={copy} /></View>
        <View style={{ flex: 1.3 }}><Btn title="Share brief" onPress={share} /></View>
      </View>
    </ScrollView>
  );
}
const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.bg, padding: 18, paddingTop: 58 },
  back: { width: 40, height: 40, borderRadius: 13, backgroundColor: theme.card, borderWidth: 1, borderColor: theme.line, alignItems: 'center', justifyContent: 'center', marginBottom: 12 },
  eyebrow: { fontSize: 11.5, letterSpacing: 1.5, textTransform: 'uppercase', fontWeight: '600', color: theme.muted },
  h2: { fontFamily: theme.fonts.serif, fontSize: 23, marginBottom: 12 },
  paper: { backgroundColor: '#fff', borderRadius: 18, padding: 22, borderWidth: 1, borderColor: theme.line },
  pt: { fontFamily: theme.fonts.serif, fontSize: 23 },
  small: { fontSize: 12, color: theme.muted, marginTop: 5 },
  h5: { fontSize: 10.5, letterSpacing: 1.5, color: theme.muted, marginTop: 18, marginBottom: 8, fontWeight: '600' },
  obs: { flexDirection: 'row', gap: 10, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: theme.line },
  n: { width: 22, height: 22, borderRadius: 7, alignItems: 'center', justifyContent: 'center' },
  interp: { padding: 12, borderRadius: 12, backgroundColor: theme.card2, fontFamily: theme.fonts.serif, fontSize: 15.5 },
  box: { width: 20, height: 20, borderRadius: 6, borderWidth: 1.5, borderColor: theme.faint, alignItems: 'center', justifyContent: 'center' },
  foot: { marginTop: 16, fontSize: 11.5, color: theme.muted },
});
