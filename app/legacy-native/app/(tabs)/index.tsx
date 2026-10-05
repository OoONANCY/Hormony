// Today — pixel port of s-today: header, CycleRing, UnlockCard, CheckIn, Quest, stats.
import React, { useEffect, useState } from 'react';
import { ScrollView, View, Text, StyleSheet, Pressable } from 'react-native';
import { useRouter } from 'expo-router';
import { theme } from '../../src/theme';
import { Card, Btn, Icon, Iridescent } from '../../src/components/ui';
import { CycleRing } from '../../src/components/CycleRing';
import { api } from '../../src/api';
import { useGame } from '../../src/game';

export default function Today() {
  const router = useRouter();
  const { xp, streak, evidence, unlocked, quest, badges, addXP, earn, completeQuest, bumpEvidence, unlock } = useGame();
  const [timeline, setTimeline] = useState<any>(null);
  const [summary, setSummary] = useState<any>(null);
  const [energy, setEnergy] = useState(2);
  const [sleepH, setSleepH] = useState(6.5);
  const [checked, setChecked] = useState(false);
  const [tags, setTags] = useState<string[]>([]);

  useEffect(() => {
    api.timeline('nancy', 90).then(setTimeline).catch(() => {});
    api.summary('nancy').then(setSummary).catch(() => {});
  }, []);

  const events = timeline?.events ?? [];
  const cycleDay = 24; // Sep 29 with starts Jun14/Jul12/Aug9/Sep6 (plan test)
  const FACES = [['😩', 'Drained'], ['😴', 'Tired'], ['😐', 'Okay'], ['🙂', 'Good'], ['⚡', 'Energized']];

  const saveCheckin = async () => {
    try {
      await api.createEvent('nancy', { type: 'sleep', name: 'Sleep', value: sleepH, unit: 'h', date: '2026-09-28' });
      if (energy <= 1) await api.createEvent('nancy', { type: 'symptom', name: 'Fatigue', severity: 6, date: '2026-09-29' });
    } catch {}
    setChecked(true);
    addXP(35);
    completeQuest('checkin');
    if (!unlocked) {
      bumpEvidence(20);
      if (evidence + 20 >= 100) { unlock(); earn('pattern'); }
    }
  };

  return (
    <ScrollView style={styles.screen} contentContainerStyle={{ paddingBottom: 130 }}>
      <View style={styles.hdr}>
        <View>
          <Text style={styles.eyebrow}>Tuesday · Sep 29</Text>
          <Text style={styles.h1}>Hey Nancy,{'\n'}<Text style={{ fontFamily: theme.fonts.serif, fontStyle: 'italic', color: theme.plum }}>welcome back</Text></Text>
        </View>
        <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
          <View style={styles.streak}><Text>🔥 {streak}</Text></View>
          <Pressable onPress={() => router.push('/(tabs)/me')} style={styles.avatar}><Text style={{ fontFamily: theme.fonts.serif, fontSize: 17, color: theme.plumDark }}>N</Text></Pressable>
        </View>
      </View>

      <Card style={{ padding: 14 }}>
        <CycleRing cycleDay={cycleDay} events={events} starts={timeline?.cycle_starts ?? []} />
        <View style={styles.legend}>
          <Text>● Symptoms  </Text><Text>— Short sleep  </Text><Text>● Lab draw</Text>
        </View>
      </Card>

      <Card>
        <View style={{ flexDirection: 'row', gap: 12, alignItems: 'center' }}>
          <Iridescent size={44}><Icon name={unlocked ? 'sparkle' : 'lock'} size={20} color={theme.plumDark} /></Iridescent>
          <View style={{ flex: 1 }}>
            <Text style={styles.eyebrow}>{unlocked ? 'Pattern unlocked' : 'Pattern forming'}</Text>
            <Text style={styles.h3}>{unlocked ? 'Your fatigue has a rhythm' : 'Something about your fatigue…'}</Text>
          </View>
          <Text style={styles.evPct}>{evidence}%</Text>
        </View>
        <Text style={[styles.blur, !unlocked && { opacity: 0.6 }]}>Your fatigue follows your cycle, and has come more often since Aug 16.</Text>
        <View style={styles.meter}><View style={[styles.fill, { width: `${evidence}%` }]} /></View>
        {unlocked ? (
          <View style={{ flexDirection: 'row', gap: 10, marginTop: 16 }}>
            <View style={{ flex: 1.5 }}><Btn title="Ask the agents why" icon="sparkle" onPress={() => router.push('/debate')} /></View>
            <View style={{ flex: 1 }}><Btn title="See insight" kind="ghost" onPress={() => router.push('/insight')} /></View>
          </View>
        ) : (
          <Text style={styles.small}>Log today's check-in to unlock it.</Text>
        )}
      </Card>

      <Card>
        {!checked ? (
          <>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}><View><Text style={styles.eyebrow}>Daily check-in</Text><Text style={styles.h2}>How are you <Text style={{ fontStyle: 'italic', color: theme.plum }}>today?</Text></Text></View><Text style={styles.xpTag}>+35 XP</Text></View>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 14, marginTop: 14 }}>
              <Text style={{ fontSize: 28 }}>{FACES[energy][0]}</Text>
              <Pressable style={{ flex: 1, height: 44, backgroundColor: theme.card2, borderRadius: 12, justifyContent: 'center', paddingHorizontal: 12 }} onPress={() => setEnergy((energy + 1) % 5)}>
                <Text>Energy: {FACES[energy][1]} (tap to change)</Text>
              </Pressable>
            </View>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 10 }}>
              <Pressable onPress={() => setSleepH(Math.max(3, sleepH - 0.5))} style={styles.stepBtn}><Text style={{ fontSize: 22 }}>−</Text></Pressable>
              <Text style={{ flex: 1, textAlign: 'center', fontSize: 22 }}>{sleepH.toFixed(1)}h</Text>
              <Pressable onPress={() => setSleepH(Math.min(11, sleepH + 0.5))} style={styles.stepBtn}><Text style={{ fontSize: 22 }}>+</Text></Pressable>
            </View>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 10 }}>
              {['Fatigue', 'Anxiety', 'Headache', 'Bloating'].map((t) => (
                <Pressable key={t} onPress={() => setTags(tags.includes(t) ? tags.filter((x) => x !== t) : [...tags, t])} style={[styles.chip, tags.includes(t) && styles.chipOn]}><Text>{t}</Text></Pressable>
              ))}
            </View>
            <View style={{ marginTop: 16 }}><Btn title="Save check-in" icon="check" onPress={saveCheckin} /></View>
          </>
        ) : (
          <Text style={styles.h3}>Checked in for today ✓</Text>
        )}
      </Card>

      <Card>
        <Text style={styles.eyebrow}>Today's quest</Text>
        <Text style={styles.h3}>{quest.checkin && quest.timeline && quest.ask ? 'Quest complete ✦' : 'Become a pattern detective'}</Text>
        {[['checkin', 'Daily check-in', '+35'], ['timeline', 'Explore your timeline', '+10'], ['ask', 'Ask the agents a question', '+50']].map(([k, t, x]: any) => (
          <View key={k} style={{ flexDirection: 'row', gap: 12, paddingVertical: 11, alignItems: 'center' }}>
            <View style={[styles.qCheck, (quest as any)[k] && styles.qOk]}><Icon name="check" size={14} color={theme.plumDark} /></View>
            <Text style={{ flex: 1 }}>{t}</Text><Text style={styles.xpTag}>{x} XP</Text>
          </View>
        ))}
      </Card>

      <View style={{ flexDirection: 'row', gap: 10 }}>
        {[[91, 'days tracked'], [summary?.days_tracked ?? 91, 'data points'], [10, 'lab values']].map(([v, l]: any, i: number) => (
          <View key={i} style={styles.stat}><Text style={styles.statB}>{v}</Text><Text style={styles.statL}>{l}</Text></View>
        ))}
      </View>
    </ScrollView>
  );
}
const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.bg, padding: 18, paddingTop: 58 },
  hdr: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 18 },
  eyebrow: { fontSize: 11.5, letterSpacing: 1.5, textTransform: 'uppercase', fontWeight: '600', color: theme.muted, fontFamily: theme.fonts.sans },
  h1: { fontFamily: theme.fonts.serif, fontSize: 33, lineHeight: 36, marginTop: 6 },
  h2: { fontFamily: theme.fonts.serif, fontSize: 23 },
  h3: { fontSize: 15.5, fontWeight: '600' },
  small: { fontSize: 13, color: theme.muted, marginTop: 12 },
  streak: { paddingHorizontal: 13, height: 38, borderRadius: 99, backgroundColor: '#F3EAF6', justifyContent: 'center' },
  avatar: { width: 46, height: 46, borderRadius: 23, backgroundColor: '#EFE4F5', alignItems: 'center', justifyContent: 'center' },
  legend: { flexDirection: 'row', justifyContent: 'center', marginTop: 6 },
  evPct: { fontSize: 22, fontWeight: '300' },
  blur: { fontFamily: theme.fonts.serif, fontSize: 21, marginVertical: 14 },
  meter: { height: 10, borderRadius: 99, backgroundColor: theme.sunk, overflow: 'hidden' },
  fill: { height: '100%', backgroundColor: theme.plum, borderRadius: 99 },
  xpTag: { fontSize: 12, fontWeight: '600', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 99, backgroundColor: '#F3EAF6', color: theme.plumDark },
  stepBtn: { width: 44, height: 44, borderRadius: 14, backgroundColor: theme.card2, alignItems: 'center', justifyContent: 'center' },
  chip: { paddingHorizontal: 14, height: 36, borderRadius: 99, borderWidth: 1, borderColor: theme.line2, justifyContent: 'center' },
  chipOn: { backgroundColor: 'rgba(196,97,79,0.1)' },
  qCheck: { width: 28, height: 28, borderRadius: 14, borderWidth: 1.5, borderColor: theme.line2, alignItems: 'center', justifyContent: 'center' },
  qOk: { backgroundColor: '#EFE4F5' },
  stat: { flex: 1, padding: 14, borderRadius: 18, backgroundColor: theme.card, borderWidth: 1, borderColor: theme.line },
  statB: { fontSize: 26, fontWeight: '300' },
  statL: { fontSize: 12, color: theme.muted },
});
