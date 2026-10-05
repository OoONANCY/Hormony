import React from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { LinearGradient } from 'expo-linear-gradient';
import { theme } from '../theme';

export const ICON_PATHS: Record<string, string> = {
  home: 'M3.5 10.5 12 4l8.5 6.5V20a1 1 0 0 1-1 1H15v-6H9v6H4.5a1 1 0 0 1-1-1z',
  timeline: 'M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01',
  sparkle: 'M12 3l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.4zM19 15.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z',
  bulb: 'M9 18h6M10 21h4M12 3a6 6 0 0 0-3.6 10.8c.7.5 1.1 1.3 1.1 2.1V16h5v-.1c0-.8.4-1.6 1.1-2.1A6 6 0 0 0 12 3z',
  user: 'M12 8a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21c1.5-4 4.5-6 8-6s6.5 2 8 6',
  flask: 'M9 3h6M10 3v6.2L4.6 18.4A1.8 1.8 0 0 0 6.2 21h11.6a1.8 1.8 0 0 0 1.6-2.6L14 9.2V3M7.2 15h9.6',
  pulse: 'M3 12h4l2.5-6 5 12 2.5-6h4',
  cycle: 'M12 12m-8.5 0a8.5 8.5 0 1 0 17 0a8.5 8.5 0 1 0-17 0',
  pill: 'M10.5 20.5l10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7zM8 8l8 8',
  moon: 'M20 14.5A8.5 8.5 0 1 1 9.5 4a6.8 6.8 0 0 0 10.5 10.5z',
  plus: 'M12 5v14M5 12h14',
  chev: 'M9 6l6 6-6 6',
  back: 'M15 6l-6 6 6 6',
  x: 'M6 6l12 12M18 6 6 18',
  check: 'M5 12.5l4.5 4.5L19 7',
  lock: 'M5 11h14a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-8a1 1 0 0 1 1-1zM8 11V8a4 4 0 0 1 8 0v3',
  share: 'M12 15V3M7 8l5-5 5 5M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6',
  copy: 'M8 8h12v12H8zM16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2',
  graph: 'M6 6m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0M18 8m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0M10 18m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0M8.5 6.4l7 1.2M7 8.3l2.2 7.3M16.6 10l-5 6',
  doc: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M9 13h6M9 17h4',
  alert: 'M12 3.5 21.5 20h-19zM12 10v4.5M12 17.2v.01',
  scale: 'M12 4v16M8 20h8M5 7h14M5 7l-2.8 6.5a3.2 3.2 0 0 0 5.6 0zM19 7l-2.8 6.5a3.2 3.2 0 0 0 5.6 0z',
  bolt: 'M13 2 4 14h7l-1 8 9-12h-7z',
};

export function Icon({ name, size = 20, color = theme.ink }: { name: string; size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
      <Path d={ICON_PATHS[name] ?? ICON_PATHS.sparkle} />
    </Svg>
  );
}

export function Card({ children, style }: any) {
  return <View style={[styles.card, style]}>{children}</View>;
}
export function Pill({ children, pearl }: any) {
  return (
    <View style={[styles.pill, pearl && styles.pearl]}>
      <Text style={[styles.pillText, pearl && { color: theme.plumDark }]}>{children}</Text>
    </View>
  );
}
export function Btn({ title, onPress, kind = 'primary', icon }: any) {
  return (
    <Pressable onPress={onPress} style={[styles.btn, kind === 'primary' ? styles.primary : kind === 'gold' ? styles.gold : styles.ghost]}>
      {icon ? <Icon name={icon} size={18} color={kind === 'primary' ? '#fff' : theme.ink} /> : null}
      <Text style={[styles.btnText, kind === 'ghost' ? { color: theme.ink } : kind === 'gold' ? { color: theme.plumDark } : { color: '#fff' }]}>{title}</Text>
    </Pressable>
  );
}
export function Iridescent({ size = 60, children }: any) {
  // Pearl gradient fallback (static linear = never-neon, iridescent). Skia sweep used where available.
  return (
    <View style={{ width: size, height: size, borderRadius: size / 2, overflow: 'hidden' }}>
      <LinearGradient colors={['#f2c9e2', '#cdbff5', '#b6dcf2', '#bfead6', '#f2e1b6', '#f1c3cf']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={{ ...StyleSheet.absoluteFillObject }} />
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: theme.card, borderRadius: 22, borderWidth: 1, borderColor: theme.line, padding: 18, marginBottom: 14, shadowColor: '#1E1A22', shadowOpacity: 0.08, shadowRadius: 16, shadowOffset: { width: 0, height: 8 }, elevation: 2 },
  pill: { flexDirection: 'row', alignItems: 'center', height: 26, paddingHorizontal: 10, borderRadius: 99, backgroundColor: theme.card2, borderWidth: 1, borderColor: theme.line },
  pearl: { backgroundColor: '#F3EAF6' },
  pillText: { fontSize: 12, fontWeight: '500', color: theme.ink2, fontFamily: theme.fonts.sans },
  btn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, height: 48, paddingHorizontal: 20, borderRadius: 14 },
  primary: { backgroundColor: theme.plum },
  ghost: { backgroundColor: theme.card, borderWidth: 1, borderColor: theme.line2 },
  gold: { backgroundColor: '#EFE4F5' },
  btnText: { fontSize: 15, fontWeight: '500', fontFamily: theme.fonts.sans },
});
