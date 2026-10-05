export const API = process.env.EXPO_PUBLIC_API_URL ?? 'http://192.168.1.20:8000';

export interface EventOut {
  id: string; date: string; type: string; name: string; code?: string | null;
  value?: number | null; unit?: string | null; severity?: number | null;
  note: string; source: string; source_ref?: string | null;
  cycle_day?: number | null; phase?: string | null;
}
export interface TimelineOut { events: EventOut[]; cycle_starts: string[]; today: string }
export interface SummaryOut { counts: Record<string, number>; days_tracked: number }

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(`API ${r.status}: ${await r.text()}`);
  return r.json() as Promise<T>;
}

export const api = {
  health: () => fetch(`${API}/health`).then(j<{ ok: boolean }>),
  timeline: (pid = 'nancy', days = 90, types = '') =>
    fetch(`${API}/patients/${pid}/timeline?days=${days}${types ? `&types=${types}` : ''}`).then(j<TimelineOut>),
  summary: (pid = 'nancy') => fetch(`${API}/patients/${pid}/summary`).then(j<SummaryOut>),
  createEvent: (pid: string, body: any) =>
    fetch(`${API}/patients/${pid}/events`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(j<EventOut>),
  createAnalysis: (question: string, active_agents: string[], patient_id = 'nancy') =>
    fetch(`${API}/analyses`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ patient_id, question, active_agents }) }).then(j<{ id: string }>),
  getAnalysis: (id: string) => fetch(`${API}/analyses/${id}`).then(j<any>),
  streamUrl: (id: string) => `${API}/analyses/${id}/stream`,
};
