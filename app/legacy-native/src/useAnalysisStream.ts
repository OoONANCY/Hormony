import { useEffect, useReducer } from 'react';
import EventSource from 'react-native-sse';
import { api } from './api';

export interface AnalysisState {
  step: number; stepLabel: string;
  ledger: Record<string, number> | null;
  thoughts: Record<string, string[]>;
  hypotheses: Record<string, any>;
  skipped: Record<string, boolean>;
  discordance: any | null;
  messages: { agent: string; text: string; evidence_ids?: string[] }[];
  verdict: any | null;
  done: boolean; error: string | null;
}
export const initialAnalysis: AnalysisState = {
  step: 0, stepLabel: 'Scoping your evidence ledger', ledger: null,
  thoughts: { lab: [], symptom: [], cycle: [] }, hypotheses: {}, skipped: {},
  discordance: null, messages: [], verdict: null, done: false, error: null,
};
const STEPS = ['Scoping your evidence ledger', 'Specialists analyzing independently', 'Discordance engine comparing conclusions', 'Agents debating the evidence', 'Reasoning critic reviewing'];

function reduceAnalysis(s: AnalysisState, e: any): AnalysisState {
  switch (e.type) {
    case 'step': return { ...s, step: e.index ?? 0, stepLabel: e.label ?? STEPS[e.index ?? 0] };
    case 'ledger': return { ...s, ledger: e.counts, step: 1, stepLabel: STEPS[1] };
    case 'thought': return { ...s, thoughts: { ...s.thoughts, [e.agent]: [...(s.thoughts[e.agent] ?? []), e.text] } };
    case 'hypothesis': return { ...s, hypotheses: { ...s.hypotheses, [e.agent]: e } };
    case 'agent_skipped': return { ...s, skipped: { ...s.skipped, [e.agent]: true } };
    case 'discordance': return { ...s, discordance: e, step: 2, stepLabel: STEPS[2] };
    case 'message': return { ...s, messages: [...s.messages, e], step: 3, stepLabel: STEPS[3] };
    case 'verdict': return { ...s, verdict: e, step: 4, stepLabel: STEPS[4] };
    case 'done': return { ...s, done: true, step: 4, stepLabel: 'Analysis complete · uncertainty preserved' };
    case 'error': return { ...s, error: e.message ?? 'error' };
    default:
      if (e.headline && e.overall_confidence !== undefined) return { ...s, verdict: e, step: 4, stepLabel: STEPS[4] };
      return s;
  }
}

export function useAnalysisStream(runId: string | null) {
  const [s, dispatch] = useReducer(reduceAnalysis, initialAnalysis);
  useEffect(() => {
    if (!runId) return;
    const es = new EventSource(api.streamUrl(runId));
    es.addEventListener('message', (ev: any) => {
      try { if (ev.data) dispatch(JSON.parse(ev.data)); } catch {}
    });
    es.addEventListener('error', () => dispatch({ type: 'error', message: 'Connection lost' } as any));
    return () => es.close();
  }, [runId]);
  return s;
}
