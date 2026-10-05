import React from 'react';
import { ScrollView, View, Text, StyleSheet, Pressable } from 'react-native';
import { useRouter } from 'expo-router';
import { theme } from '../../src/theme';
import { Card, Icon } from '../../src/components/ui';
import { useGame } from '../../src/game';

export default function Insights() {
  const router = useRouter();
  const { unlocked, evidence } = useGame();
  return (
    <ScrollView style={styles.screen} contentContainerStyle={{ paddingBottom: 130 }}>
      <Text style={styles.eyebrow}>{unlocked ? '1 of 4 unlocked' : '0 of 4 unlocked'}</Text>
      <Text style={styles.h1}>Your <Text style={{ fontStyle: 'italic', color: theme.plum }}>insights</Text></Text>
      <Pressable onPress={() => (unlocked ? router.push('/insight') : router.push('/(tabs)'))}>
        <Card>
          <Text style={styles.eyebrow}>{unlocked ? 'Unlocked' : `${evidence}% there`}</Text>
          <Text style={styles.ttl}>Your fatigue follows your cycle, and has come more often since Aug 16.</Text>
          <View style={styles.meter}><View style={[styles.fill, { width: `${unlocked ? 100 : evidence}%` }]} /></View>
        </Card>
      </Pressable>
      {[['Sleep × cycle rhythm', 60], ['Headache timing', 35], ['Anxiety and your cycle', 45]].map(([t, p]: any) => (
        <Card key={t}><Text style={styles.small}>{t}</Text><Text style={styles.ttl}>Keep logging to unlock.</Text><View style={styles.meter}><View style={[styles.fill, { width: `${p}%` }]} /></View></Card>
      ))}
      <Text style={styles.h3}>Go deeper</Text>
      <Pressable onPress={() => router.push('/graph')}><Card><View style={{ flexDirection: 'row', gap: 14, alignItems: 'center' }}><Icon name="graph" size={22} color={theme.plum} /><View><Text style={styles.h3}>Hypothesis graph</Text><Text style={styles.small}>Drag factors. Tap a link for evidence.</Text></View></View></Card></Pressable>
      <Pressable onPress={() => router.push('/brief')}><Card><View style={{ flexDirection: 'row', gap: 14, alignItems: 'center' }}><Icon name="doc" size={22} color={theme.plum} /><View><Text style={styles.h3}>Clinician brief</Text><Text style={styles.small}>Observations + questions for your doctor.</Text></View></View></Card></Pressable>
    </ScrollView>
  );
}
const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.bg, padding: 18, paddingTop: 58 },
  eyebrow: { fontSize: 11.5, letterSpacing: 1.5, textTransform: 'uppercase', fontWeight: '600', color: theme.muted },
  h1: { fontFamily: theme.fonts.serif, fontSize: 33, marginBottom: 14 },
  h3: { fontSize: 15.5, fontWeight: '600', marginTop: 16 },
  ttl: { fontFamily: theme.fonts.serif, fontSize: 19, marginVertical: 10 },
  small: { fontSize: 13, color: theme.muted },
  meter: { height: 10, borderRadius: 99, backgroundColor: theme.sunk, overflow: 'hidden' },
  fill: { height: '100%', backgroundColor: theme.plum },
});
