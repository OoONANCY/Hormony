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
| **Profiles** | Start your own record (it starts empty, on the real date) or explore the fictional demo. Switch between profiles, or delete your data, from Me |
| **Lab reports** | Upload a PDF or take a photo. Hormony reads the results, you check and correct them, and each saved value links back to the original file |
| **Me** | Profiles, badges, per-agent access toggles (consent), data sources, report upload, CSV/JSON import |

## Architecture

```
Expo app (iOS / Android / web)
  └─ WebView running app/web/hormony-app.html  ── haptics, share, clipboard, back button via a native bridge
        │  REST + Server-Sent Events
FastAPI backend (backend/)
  ├─ Accounts: email + password (argon2), 24-hour signed tokens · each account owns its profiles
  ├─ Profiles: a shared, read-only demo + personal records on the real date, each with its own cycle length
  ├─ Evidence ledger (SQLite or PostgreSQL) ── CSV/JSON import + lab reports, all with provenance
  ├─ Report reader: PDF text → text LLM (or rules) · photos/scans → vision LLM · you confirm before saving
  ├─ compute_stats(): every number, date and analyte, computed in Python
  └─ LangGraph workflow
        scope → [Lab | Symptom | Cycle] in parallel → discordance → debate (if conflict) → critic → report
        LLM: OpenRouter (e.g. NVIDIA Nemotron) · Anthropic Claude · offline demo engine
```

- **Agents interpret facts; they never compute them.** Each specialist sees only its own facts.
- **Every record has an owner:** you can read your own profiles and the shared demo. Someone else's profile, analysis or report answers "not found", and only the owner can change a profile.
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
  hormony/ledger/        Cycle maths, profiles, ledger access, importer, demo seed
  hormony/reports/       Lab-report reading: PDF text, page images, analyte names, rule-based fallback
  hormony/outputs/       Report, why-chain, hypothesis graph, clinician brief
  hormony/auth.py        Accounts: passwords, tokens, and who may read or change which profile
  hormony/api/           HTTP routes (auth, profiles, events, reports, analyses + SSE)
  uploads/               Original uploaded reports, one folder per profile (gitignored: personal health data)
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
echo "HORMONY_AUTH_SECRET=$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(48))')" >> .env
.venv/bin/python -m hormony.ledger.seed     # optional: the demo profile "Nancy" (130 example records)
.venv/bin/python -m uvicorn hormony.api.main:app --host 0.0.0.0 --port 8000
```

Run these from inside `backend/` (that's where `.env` is read). Check it:

```bash
curl localhost:8000/health
# {"ok": true, "db": "ok", "llm": "openrouter:nvidia/nemotron-3-super-120b-a12b:free",
#  "vision": "openrouter:nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"}
```

Existing databases are upgraded in place when the backend starts (no data is lost). The server refuses to start without `HORMONY_AUTH_SECRET`: with a missing or default secret, anyone could sign in as anyone.

### 2. App on your phone (Expo Go)

```bash
cd app
yarn install
ipconfig getifaddr en0                      # macOS: your laptop's Wi-Fi IP, e.g. 192.168.1.20
EXPO_PUBLIC_API_URL=http://192.168.1.20:8000 yarn start --lan
```

Scan the QR code in the terminal with your phone (iPhone Camera or Expo Go's scanner), or enter `exp://<your-ip>:8081` in Expo Go. The phone must be on the same Wi-Fi as the laptop.

On first launch the app asks you to **create an account** (or sign in), then whether to **start your own record** or **explore the demo**. It remembers both on that phone; sign out from Me. Sessions last 24 hours, after which it asks for your password again and reopens where you were.

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
| **Photos of reports** | `HORMONY_VISION_MODEL` (default `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`), used through your `OPENROUTER_API_KEY`. Without a key, text PDFs are still read (by rules), but photos and scanned PDFs are refused with a clear message |

- **Automatic choice:** with `HORMONY_LLM` empty, the provider is picked from your keys: OpenRouter first, then Anthropic, then demo.
- **No silent fallback:** if the configured provider is broken (missing or invalid key, no credits), `POST /analyses` returns 503 with the reason. It never quietly switches to demo answers.
- **Model compatibility:** OpenRouter models with strict JSON-schema support get it. Others get the schema in the prompt, plus validation and one repair attempt.
- **Free-tier limits:** free OpenRouter models are rate-limited, and each analysis makes 7 calls. If an agent shows "Unavailable", wait a minute or use a paid model (drop `:free`).
- **Privacy:** on free models, prompts (which contain your health records, and the report pages you upload) may be logged by the serving provider. For real data, use a provider and model that don't retain prompts. The app's Me screen and setup screen name the models in use.

## Your record and the demo

- **Accounts:** sign up with an email and a password (8+ characters). Each account sees only its own profiles plus the demo. After 5 wrong passwords, sign-in for that email pauses for 15 minutes. Profiles created before this server had accounts belong to the first account registered on it.

- **Your own record** starts empty. Setup asks for three things: a name, the day your last period started (within the last 120 days), and your usual cycle length (21–45 days). It runs on the real date, and cycle phases and the late-luteal window follow your cycle length. XP, streaks and badges start at zero and are kept per profile on that phone.
- **Lab reports:** + → Lab report, or Me → Upload a lab report. Pick a PDF or image, or take a photo. Hormony shows what it read: you can untick rows, fix values, units or the collection date, and nothing is saved until you confirm. Each saved value's source is `Lab report: <file>`, and its record sheet has **Open the original report**. Uploading the same file again is detected. Files are stored under `backend/uploads/<profile>/`.
- **Delete my data** (Me) removes the profile's records, analyses and uploaded files from the server.

## Demo data and modes

- **The demo is shared and read-only on the server:** anyone signed in can view and analyse it, but what you log there stays on your phone, so one person's entries never show up for another.
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

Everything except `/health`, `/auth/register`, `/auth/login` and report links needs `Authorization: Bearer <access_token>`.

| Method | Path | |
|---|---|---|
| GET | `/health` | Database status, active LLM provider and the vision model (or `null`) |
| POST | `/auth/register`, `/auth/login` | `{email, password}`, returns `{access_token, expires_in, user_id, email}` |
| GET | `/auth/me` | The signed-in account |
| GET / POST | `/profiles` | Your profiles plus the demo, or create one: `{name, last_period_start, cycle_length}` |
| GET / DELETE | `/profiles/{id}` | One profile with record counts, or delete a personal profile and all its data |
| POST | `/patients/{id}/reports` | Upload a PDF or image (≤ 15 MB). Returns the extracted rows for review; nothing is saved yet |
| POST | `/patients/{id}/reports/{report}/confirm` | `{rows: [...]}`, the reviewed rows. Saves them as lab records linked to the file |
| GET | `/patients/{id}/reports/{report}/file` | The original uploaded file |
| POST | `/patients/{id}/reports/{report}/link` | A 5-minute link (`/reports/files/<token>`) that opens the file without the header, e.g. in a phone browser |
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
| "Your session has expired" | Sign in again; sessions last 24 hours. Your records are untouched |
| A check-in in the demo disappears after switching profiles | Expected: the demo is shared and read-only on the server, so what you log there stays on the phone until you leave it |
| "Can't reach Hormony" on launch | Same cause as below. Your own record is never replaced by demo data; tap **Try again** once the backend is up |
| App says "Offline · showing demo data" | The phone can't reach the API. Check that both are on the same Wi-Fi, that `EXPO_PUBLIC_API_URL` uses the laptop's IP (not `localhost`), and that the macOS firewall allows incoming connections for Python and Node |
| "Project is incompatible with this version of Expo Go" | Update Expo Go (the project uses SDK 57) |
| Backend won't start: `HORMONY_AUTH_SECRET must be ...` | Add a secret to `backend/.env` (the `echo` line in Quick start), then start it again |
| `/health` shows `misconfigured: ...` | Fix the key or provider named in the message in `backend/.env`, then restart the backend |
| An agent shows "Unavailable" | Usually a provider rate limit; the other agents and the critic still finish |
| A photo of a report is refused | Photos and scanned PDFs need a vision model: set `OPENROUTER_API_KEY` (and optionally `HORMONY_VISION_MODEL`) and restart the backend. HEIC images can't be read; share the photo as JPEG |
| Changes to `app/web/hormony-app.html` don't appear | Run `yarn build:web` (it also runs automatically on `yarn start`) and reload the app |

## Roadmap

Next up:
- Password reset and email verification.
- Reminders for check-ins and for experiments the critic suggests.

Later:
- FHIR/EHR import, a digital twin, prediction, a wider set of agents, and a clinician workflow.
