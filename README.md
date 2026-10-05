# Hormony: Hormone Insight Engine

A privacy-conscious app that puts your hormone labs, symptoms, cycle, sleep and medication changes on one longitudinal timeline. Three specialist AI agents (Lab, Symptom, Cycle) analyze that timeline independently. Hormony then shows where they **disagree** instead of averaging them away, and a reasoning critic weighs the evidence. Every conclusion traces back to the exact records it came from.

> **Not a diagnosis.** Hormony surfaces time-based associations in self-reported and uploaded data so you can have a better-informed conversation with a clinician.

## What it does

| | |
|---|---|
| **Today** | Cycle ring (drag to replay the cycle), daily check-in, streaks, quests, XP and levels, insight unlocks |
| **Timeline** | Swim lanes for cycle / labs / symptoms / sleep / meds, hormone trend charts, an evidence ledger with provenance for every record |
| **Ask** | A live multi-agent analysis: 3 independent specialists → discordance engine → rebuttal debate → reasoning critic |
| **Insight + "Why?"** | Headline with confidence, and an evidence chain from sources to observations to reasoning to confidence to alternatives |
| **Hypothesis graph** | Draggable graph of associated factors. Every link cites ledger records; links nobody assessed carry no confidence |
| **Clinician brief** | One-page summary with observed patterns, interpretation and questions to ask, ready to copy or share |
| **Me** | Badges, per-agent access toggles (consent), data sources, CSV/JSON import |

## Architecture

```
Expo app (iOS / Android / web)
  └─ WebView running app/web/hormony-app.html  ── haptics, share, clipboard, back button via a native bridge
        │  REST + Server-Sent Events
FastAPI backend (backend/)
  ├─ Evidence ledger (SQLite or PostgreSQL) ── CSV/JSON import with provenance
  ├─ compute_stats(): every number, date and analyte, computed in Python
  └─ LangGraph workflow
        scope → [Lab | Symptom | Cycle] in parallel → discordance → debate (if conflict) → critic → report
        LLM: OpenRouter (e.g. NVIDIA Nemotron) · Anthropic Claude · offline demo engine
```

- **Agents interpret facts; they never compute them.** Each specialist sees only its own facts.
- **Provenance guard:** evidence IDs that aren't in the ledger are removed, and confidence is capped when nothing verifiable remains.
- **Single run:** each analysis runs the graph exactly once (7 LLM calls). The result you see streaming is the result that gets saved.

## Repository layout

```
app/                     Expo app (TypeScript, expo-router)
  app/index.tsx          WebView shell + native bridge
  web/hormony-app.html   The UI (markup, styles, interaction and the live-data layer)
  scripts/build-web.mjs  Bundles the HTML into the app (runs on install/start)
  legacy-native/         Earlier React Native screens (unused, kept for reference)
backend/                 FastAPI + LangGraph
  hormony/agents/        LLM providers, prompts, graph nodes, discordance, provenance guard
  hormony/analysis/      Deterministic facts + stats
  hormony/ledger/        Cycle maths, ledger access, importer, demo seed
  hormony/outputs/       Report, why-chain, hypothesis graph, clinician brief
  hormony/api/           HTTP routes (events, analyses + SSE)
  sample_data/           Example CSV + recorded demo run (for replay mode)
  tests/                 Offline test suite
```

## Prerequisites

- **Python 3.10+**
- **Node 20+** and **yarn** (or npm)
- **Expo Go** on your phone, matching **Expo SDK 57** (update it from the App Store / Play Store)
- Optional: an **OpenRouter** or **Anthropic** API key. Without one, the backend uses an offline demo engine and says so.
- Optional: Docker, if you prefer PostgreSQL to SQLite

## Quick start

### 1. Backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env                        # then set your LLM provider/key (see below)
.venv/bin/python -m hormony.ledger.seed     # loads the demo profile "nancy" (130 example records)
.venv/bin/python -m uvicorn hormony.api.main:app --host 0.0.0.0 --port 8000
```

Run these from inside `backend/` (that's where `.env` is read). Check it:

```bash
curl localhost:8000/health
# {"ok": true, "db": "ok", "llm": "openrouter:nvidia/nemotron-3-super-120b-a12b:free"}
```

### 2. App on your phone (Expo Go)

```bash
cd app
yarn install
ipconfig getifaddr en0                      # macOS: your laptop's Wi-Fi IP, e.g. 192.168.1.20
EXPO_PUBLIC_API_URL=http://192.168.1.20:8000 yarn start --lan
```

Scan the QR code in the terminal with your phone (iPhone Camera or Expo Go's scanner), or enter `exp://<your-ip>:8081` in Expo Go. The phone must be on the same Wi-Fi as the laptop.

- If the phone can't connect, try `yarn start --tunnel` (the API URL must still be reachable from the phone).
- Without `EXPO_PUBLIC_API_URL`, the app runs on its built-in demo data.

### 3. Browser preview (optional)

Open `app/web/hormony-app.html?api=http://localhost:8000` in a browser for the same UI against your local backend. On a wide screen it shows a phone frame and a demo guide.

## Choosing the LLM

Set these in `backend/.env`. Real environment variables override the file.

| Provider | Settings |
|---|---|
| **OpenRouter** (e.g. NVIDIA Nemotron) | `OPENROUTER_API_KEY=sk-or-...` · optional `HORMONY_OPENROUTER_MODEL` (default `nvidia/nemotron-3-super-120b-a12b:free`) |
| **Anthropic** | `ANTHROPIC_API_KEY=...` (or `ant auth login` + `HORMONY_LLM=anthropic`) · optional `HORMONY_MODEL` (default `claude-opus-5`) |
| **Offline demo** | `HORMONY_LLM=demo` (the default when no key is set). Rule-based and built from your facts; no network calls |

- **Automatic choice:** with `HORMONY_LLM` empty, the provider is picked from your keys: OpenRouter first, then Anthropic, then demo.
- **No silent fallback:** if the configured provider is broken (missing or invalid key, no credits), `POST /analyses` returns 503 with the reason. It never quietly switches to demo answers.
- **Model compatibility:** OpenRouter models with strict JSON-schema support get it. Others get the schema in the prompt, plus validation and one repair attempt.
- **Free-tier limits:** free OpenRouter models are rate-limited, and each analysis makes 7 calls. If an agent shows "Unavailable", wait a minute or use a paid model (drop `:free`).
- **Privacy:** on free models, prompts (which contain your health records) may be logged by the serving provider. For real data, use a provider and model that don't retain prompts.

## Demo data and modes

- **The "nancy" profile is fictional demo data** ported from the original prototype: 91 days of labs, symptoms, sleep, 4 cycles and one medication change, with a deliberate conflict for the agents to debate. The app's "today" is fixed at `HORMONY_TODAY=2026-09-29` to match it.
- **Reset the demo:** `.venv/bin/python -m hormony.ledger.seed` (this replaces nancy's records).
- **Replay mode:** `HORMONY_DEMO_REPLAY=1` replays a recorded analysis (`sample_data/golden_run.json`) with realistic pacing, without any LLM calls. Paused agents are respected. Good as a backup for live demos.
- **Analysis from the terminal:**
  ```bash
  .venv/bin/python -m hormony.cli ask "Why have my fatigue episodes increased over the last two cycles?"
  .venv/bin/python -m hormony.cli ask "..." --pause lab     # consent toggle
  .venv/bin/python -m hormony.cli ask "..." --demo --golden sample_data/golden_run.json   # re-record the replay
  ```
- **Import your own records:** in the app, Me → Import CSV / JSON, or `POST /patients/{id}/import`. CSV columns are `date,type,name,code,value,unit,severity,note`, and `type` is one of `cycle, lab, symptom, sleep, med`. A cycle event named `Period started` marks a new cycle. See `backend/sample_data/labs.csv`.

## API

| Method | Path | |
|---|---|---|
| GET | `/health` | Database status + active LLM provider |
| GET | `/patients/{id}/timeline?days=91&types=lab,symptom` | Events with cycle day and phase, plus cycle starts |
| GET | `/patients/{id}/summary` | Counts per type |
| POST | `/patients/{id}/events` | Add one record (check-ins, manual logs) |
| POST | `/patients/{id}/import` | CSV/JSON file upload |
| POST | `/analyses` | `{patient_id, question, active_agents}`, returns `{id}` |
| GET | `/analyses/{id}/stream` | Server-Sent Events: step, ledger, thought, hypothesis, agent_skipped, discordance, message, verdict, done/error |
| GET | `/analyses/{id}` | Full saved result: facts, hypotheses, discordance, debate, verdict, report, graph, brief |

## Tests

```bash
cd backend && .venv/bin/python -m pytest            # offline: uses a temporary database and the demo engine
HORMONY_LIVE_TESTS=1 .venv/bin/python -m pytest -m live   # one real end-to-end run with your configured provider
cd app && yarn test                                  # bundles the UI + TypeScript check
```

## Troubleshooting

| Problem | Fix |
|---|---|
| App says "Offline · showing demo data" | The phone can't reach the API. Check that both are on the same Wi-Fi, that `EXPO_PUBLIC_API_URL` uses the laptop's IP (not `localhost`), and that the macOS firewall allows incoming connections for Python and Node |
| "Project is incompatible with this version of Expo Go" | Update Expo Go (the project uses SDK 57) |
| `/health` shows `misconfigured: ...` | Fix the key or provider named in the message in `backend/.env`, then restart the backend |
| An agent shows "Unavailable" | Usually a provider rate limit; the other agents and the critic still finish |
| Changes to `app/web/hormony-app.html` don't appear | Run `yarn build:web` (it also runs automatically on `yarn start`) and reload the app |

## Roadmap

Next up:
- Separate demo and personal profiles, with onboarding and the real date.
- Real lab-report reading: PDF or photo, then extracted values you confirm, with provenance back to the file.

Later:
- FHIR/EHR import, a digital twin, prediction, a wider set of agents, authentication, and a clinician workflow.
