import React, { useState } from 'react';
import { ScrollView, View, Text, StyleSheet, Pressable, TextInput } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { theme } from '../src/theme';
import { Card, Btn } from '../src/components/ui';
import { AgentCard, DiscordanceMap } from '../src/components/AgentCard';
import { api } from '../src/api';
import { useAnalysisStream } from '../src/useAnalysisStream';
import { useGame } from '../src/game';

const SUGS = ['Why have my fatigue episodes increased over the last two cycles?', 'Is my sleep changing with my cycle?', 'What changed after I started spironolactone?'];

export default function Debate() {
  const router = useRouter();
  const params = useLocalSearchParams<{ id?: string }>();
  const [runId, setRunId] = useState<string | null>((params.id as string) ?? null);
  const [q, setQ] = useState(SUGS[0]);
  const s = useAnalysisStream(runId);
  const { paused, completeQuest, earn, addXP } = useGame();

  const start = async () => {
    const active = (['lab', 'symptom', 'cycle'] as const).filter((a) => !(paused as string[]).includes(a));
    const r = await api.createAnalysis(q, active as string[]);
    setRunId(r.id);
    completeQuest('ask');
  };
  React.useEffect(() => {
    if (s.done) { earn('debate'); addXP(50); }
  }, [s.done]);

  if (!runId) {
    return (
      <ScrollView style={styles.screen}>
        <Text style={styles.eyebrow}>Ask Hormony</Text>
        <Text style={styles.h2}>What do you want to <Text style={{ fontStyle: 'italic', color: theme.plum }}>understand?</Text></Text>
        <TextInput value={q} onChangeText={setQ} multiline style={styles.box} />
        {SUGS.map((g) => (
          <Pressable key={g} onPress={() => setQ(g)} style={styles.chip}><Text style={{ fontSize: 13 }}>{g.slice(0, 42)}…</Text></Pressable>
        ))}
        <View style={{ marginTop: 16 }}><Btn title="Start analysis" icon="sparkle" onPress={start} /></View>
      </ScrollView>
    );
  }
  return (
    <ScrollView style={styles.screen} contentContainerStyle={{ paddingBottom: 40 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
        <Pressable onPress={() => router.back()} style={styles.back}><Text>✕</Text></Pressable>
        <Text style={styles.h3}>Multi-agent analysis</Text>
      </View>
      <View style={styles.steps}>{[0, 1, 2, 3, 4].map((i) => (<View key={i} style={[styles.seg, s.step >= i && styles.on]} />))}</View>
      <Text style={styles.small}>{`Step ${s.step + 1} of 5 · ${s.stepLabel}`}</Text>
      <Card><Text style={styles.eyebrow}>Your question</Text><Text style={styles.q}>{q}</Text>
        {s.ledger ? <Text style={styles.small}>{Object.values(s.ledger).reduce((a: any, b: any) => a + b, 0)} records scoped</Text> : <Text style={styles.small}>Pulling records…</Text>}
      </Card>
      {(['lab', 'symptom', 'cycle'] as const).map((a) => (
        <AgentCard key={a} agent={a} thought={s.thoughts[a] ?? []} hypothesis={s.hypotheses[a]} state={s.skipped[a] ? 'Paused' : s.hypotheses[a] ? 'Done ✓' : s.thoughts[a]?.length ? 'Thinking' : 'Queued'} />
      ))}
      {s.discordance ? <DiscordanceMap discordance={s.discordance} /> : null}
      {s.messages.map((m, i) => (
        <Card key={i}><Text style={styles.small}>{m.agent}</Text><Text>{m.text.replace(/<[^>]+>/g, '')}</Text></Card>
      ))}
      {s.verdict ? (
        <Card>
          <Text style={styles.eyebrow}>Critic verdict</Text>
          <Text style={styles.h3}>No single cause is supported.</Text>
          <Text style={{ marginTop: 8 }}>{s.verdict.summary ?? s.verdict.headline}</Text>
          <View style={{ marginTop: 16 }}><Btn title="Reveal your insight" onPress={() => router.push({ pathname: '/insight', params: { id: runId } })} /></View>
        </Card>
      ) : null}
      {s.error ? <Text style={{ color: 'red' }}>Connection lost · Retry</Text> : null}
    </ScrollView>
  );
}
const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.bg, padding: 18, paddingTop: 58 },
  eyebrow: { fontSize: 11.5, letterSpacing: 1.5, textTransform: 'uppercase', fontWeight: '600', color: theme.muted },
  h2: { fontFamily: theme.fonts.serif, fontSize: 25, marginTop: 6 },
  h3: { fontSize: 15.5, fontWeight: '600' },
  small: { fontSize: 13, color: theme.muted, marginTop: 4 },
  box: { minHeight: 96, borderRadius: 18, borderWidth: 1, borderColor: theme.line2, backgroundColor: theme.card2, padding: 14, fontFamily: theme.fonts.serif, fontSize: 19, marginTop: 16 },
  chip: { padding: 10, borderRadius: 99, borderWidth: 1, borderColor: theme.line2, marginTop: 8 },
  back: { width: 40, height: 40, borderRadius: 13, backgroundColor: theme.card, borderWidth: 1, borderColor: theme.line, alignItems: 'center', justifyContent: 'center' },
  steps: { flexDirection: 'row', gap: 6, marginVertical: 14 },
  seg: { flex: 1, height: 4, borderRadius: 99, backgroundColor: theme.sunk },
  on: { backgroundColor: theme.plum },
  q: { fontFamily: theme.fonts.serif, fontSize: 25, marginTop: 6 },
});
