import { Stack } from 'expo-router';
import { useEffect, useState } from 'react';
import * as Font from 'expo-font';
import { Newsreader_400Regular, Newsreader_400Regular_Italic } from '@expo-google-fonts/newsreader';
import { Inter_400Regular, Inter_500Medium, Inter_600SemiBold } from '@expo-google-fonts/inter';

export default function Root() {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    (async () => {
      try {
        await Font.loadAsync({ Newsreader: Newsreader_400Regular, NewsreaderItalic: Newsreader_400Regular_Italic, Inter: Inter_400Regular, InterMedium: Inter_500Medium, InterSemi: Inter_600SemiBold });
      } catch {}
      setReady(true);
    })();
  }, []);
  if (!ready) return null;
  return <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: '#F6F2EC' } }} />;
}
