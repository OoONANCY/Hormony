import React from 'react';
import { Tabs } from 'expo-router';
import { View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Icon } from '../../src/components/ui';
import { theme } from '../../src/theme';

function OrbIcon() {
  return (
    <View style={{ width: 60, height: 60, marginTop: -34, borderRadius: 30, overflow: 'hidden', borderWidth: 3, borderColor: theme.bg }}>
      <LinearGradient colors={['#f2c9e2', '#cdbff5', '#b6dcf2', '#bfead6', '#f2e1b6', '#f1c3cf']} style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
        <Icon name="sparkle" size={24} color={theme.plumDark} />
      </LinearGradient>
    </View>
  );
}

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: { position: 'absolute', left: 14, right: 14, bottom: 14, height: 68, borderRadius: 24, backgroundColor: 'rgba(255,253,249,0.86)', borderColor: theme.line },
        tabBarActiveTintColor: theme.plum,
        tabBarInactiveTintColor: theme.faint,
      }}
    >
      <Tabs.Screen name="index" options={{ title: 'Today', tabBarIcon: ({ color }) => <Icon name="home" size={21} color={color as string} /> }} />
      <Tabs.Screen name="timeline" options={{ title: 'Timeline', tabBarIcon: ({ color }) => <Icon name="timeline" size={21} color={color as string} /> }} />
      <Tabs.Screen name="ask" options={{ title: '', tabBarIcon: () => <OrbIcon /> }} />
      <Tabs.Screen name="insights" options={{ title: 'Insights', tabBarIcon: ({ color }) => <Icon name="bulb" size={21} color={color as string} /> }} />
      <Tabs.Screen name="me" options={{ title: 'Me', tabBarIcon: ({ color }) => <Icon name="user" size={21} color={color as string} /> }} />
    </Tabs>
  );
}
