import { Redirect } from 'expo-router';
export default function AskRedirect() {
  return <Redirect href="/debate?autostart=1" />;
}
