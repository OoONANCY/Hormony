import React, { useEffect, useState } from 'react';
import { ScrollView, View, Text, StyleSheet, Pressable } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { theme } from '../src/theme';
import { Card } from '../src/components/ui';
import { HypothesisGraph } from '../src/components/Graphs';
import { api } from '../src/api';

export default function GraphScreen() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [sel, setSel] = useState(0);
  useEffect(() => { if (id) api.getAnalysis(id as string).then(setData).catch(() => {}); }, [id]);
  const graph = data?.graph ?? { nodes: [], edges: [{ a: 'lut', b: 'fat', type: 'Temporal association', evidence: '13 of 16', window: 'days 20–28', confidence: 0.74, alternatives: [] }] };
  const e = graph.edges?.[sel];
  return (
    <ScrollView style={styles.screen}>
      <Pressable onPress={() => router.back()} style={styles.back}><Text>‹</Text></Pressable>
      <Text style={styles.eyebrow}>Evidence-backed</Text>
      <Text style={styles.h2}>Hypothesis <Text style={{ fontStyle: 'italic', color: theme.plum }}>graph</Text></Text>
      <Card><Text style={styles.small}>Hypotheses, not proven causes. Thicker line = more confident.</Text></Card>
      <Card><HypothesisGraph graph={graph} onEdge={() => {}} /></Card>
      {e ? (
        <Card>
          <Text style={styles.eyebrow}>Relationship</Text>
          <Text style={styles.h3}>{e.a} → {e.b}</Text>
          <Text>Type: {e.type}</Text><Text>Evidence: {e.evidence}</Text><Text>Window: {e.window}</Text><Text>Confidence: {e.confidence ?? 'Not assessable'}</Text>
        </Card>
      ) : null}
    </ScrollView>
  );
}
const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.bg, padding: 18, paddingTop: 58 },
  back: { width: 40, height: 40, borderRadius: 13, backgroundColor: theme.card, borderWidth: 1, borderColor: theme.line, alignItems: 'center', justifyContent: 'center', marginBottom: 12 },
  eyebrow: { fontSize: 11.5, letterSpacing: 1.5, textTransform: 'uppercase', fontWeight: '600', color: theme.muted },
  h2: { fontFamily: theme.fonts.serif, fontSize: 23, marginBottom: 12 },
  h3: { fontSize: 15.5, fontWeight: '600' },
  small: { fontSize: 13, color: theme.muted },
});
