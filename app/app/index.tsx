// The whole UI is the design prototype itself (web/hormony-app.html) running in a WebView, so the app
// looks exactly like the prototype. This shell only supplies the backend URL and native capabilities
// (haptics, clipboard, share sheet, opening an uploaded report, Android back button) through a small message bridge.
import React, { useCallback, useEffect, useMemo, useRef } from 'react';
import { BackHandler, Linking, Platform, Share, View } from 'react-native';
import { WebView, type WebViewMessageEvent } from 'react-native-webview';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';
import * as Clipboard from 'expo-clipboard';
import { HORMONY_HTML } from '../src/web/hormonyHtml';

// Empty API URL = the page runs on its built-in demo data, exactly like the standalone prototype.
const API_URL = (process.env.EXPO_PUBLIC_API_URL ?? '').replace(/\/+$/, '');
// Empty = the page asks who you are (start your own record or explore the demo) and remembers it on this device.
const PATIENT_ID = process.env.EXPO_PUBLIC_PATIENT_ID ?? '';
const BG = '#F6F2EC';

type BridgeMessage =
  | { type: 'haptic'; p?: number | number[] }
  | { type: 'copy'; text?: string }
  | { type: 'share'; text?: string }
  | { type: 'back'; handled?: boolean }
  | { type: 'open'; url?: string };

let lastHaptic = 0;
function haptic(p: number | number[] | undefined) {
  const now = Date.now();
  if (now - lastHaptic < 35) return; // the cycle-ring scrub fires one per day crossed
  lastHaptic = now;
  const run = Array.isArray(p)
    ? Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success)
    : (p ?? 8) <= 5
      ? Haptics.selectionAsync()
      : (p ?? 8) >= 12
        ? Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium)
        : Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
  run.catch(() => {});
}

export default function HormonyScreen() {
  const insets = useSafeAreaInsets();
  const webRef = useRef<WebView>(null);

  const html = useMemo(() => {
    const config = JSON.stringify({ apiUrl: API_URL, patientId: PATIENT_ID, native: Platform.OS !== 'web' });
    return HORMONY_HTML.replace('<script>', `<script>window.HORMONY_CONFIG=${config};</script>\n<script>`);
  }, []);

  const onMessage = useCallback((e: WebViewMessageEvent) => {
    let msg: BridgeMessage;
    try {
      msg = JSON.parse(e.nativeEvent.data);
    } catch {
      return;
    }
    switch (msg.type) {
      case 'haptic':
        haptic(msg.p);
        break;
      case 'copy':
        Clipboard.setStringAsync(String(msg.text ?? '')).catch(() => {});
        break;
      case 'share':
        Share.share({ message: String(msg.text ?? ''), title: 'Endocrine Insight Report' }).catch(() => {});
        break;
      case 'back':
        if (!msg.handled) BackHandler.exitApp();
        break;
      case 'open': {
        // Only files served by our own backend (an uploaded lab report), never arbitrary links from page content.
        const url = String(msg.url ?? '');
        if (API_URL && url.startsWith(API_URL + '/')) Linking.openURL(url).catch(() => {});
        break;
      }
    }
  }, []);

  // Android back: let the page close sheets / go back a screen first; exit only from Today.
  useEffect(() => {
    if (Platform.OS !== 'android') return;
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      webRef.current?.injectJavaScript(
        "(function(){var h=window.hormonyBack&&window.hormonyBack();window.ReactNativeWebView.postMessage(JSON.stringify({type:'back',handled:!!h}));})();true;",
      );
      return true;
    });
    return () => sub.remove();
  }, []);

  if (Platform.OS === 'web') {
    // react-native-webview has no web implementation; an iframe renders the same page.
    return (
      <View style={{ flex: 1, backgroundColor: BG }}>
        {React.createElement('iframe', { srcDoc: html, title: 'Hormony', style: { border: 0, width: '100%', height: '100%' } })}
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: BG, paddingTop: insets.top, paddingBottom: insets.bottom }}>
      <WebView
        ref={webRef}
        // baseUrl = the API origin, so the page's fetch/EventSource calls are same-origin (no CORS issues).
        source={{ html, baseUrl: API_URL || undefined }}
        originWhitelist={['*']}
        onMessage={onMessage}
        javaScriptEnabled
        domStorageEnabled
        allowFileAccess
        mixedContentMode="always"
        bounces={false}
        overScrollMode="never"
        contentInsetAdjustmentBehavior="never"
        automaticallyAdjustContentInsets={false}
        keyboardDisplayRequiresUserAction={false}
        hideKeyboardAccessoryView
        setSupportMultipleWindows={false}
        showsVerticalScrollIndicator={false}
        style={{ flex: 1, backgroundColor: BG }}
        containerStyle={{ backgroundColor: BG }}
      />
    </View>
  );
}
