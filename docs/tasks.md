# atlogs — Task Tracker

> The single tracker for atlogs: status, owners, dependencies and decisions.
> Rules for doing the work: [`AGENTS.md`](../AGENTS.md).
> ✅ = verified (evidence linked) · 🔄 = in progress · ⬜ = not started.
> Status words follow AGENTS.md §8; nothing is ✅ without evidence.

---

## Existing foundation

What the code already contains. None of it has been re-verified for atlogs yet;
a row moves to ✅ only when its test or demo evidence is linked here.

| Area | Code | Tests | Status |
|------|------|-------|--------|
| JSON connectors + 8-step ingest pipeline | `services/connectors.py`, `services/pipeline.py` | — | existing — not yet verified |
| Schema discovery | `engine/schema_discovery.py` | `test_schema_discovery.py` | existing — not yet verified |
| Entity resolution (confidence, merge bands, manual decisions) | `engine/resolution/` | `test_resolution.py`, `test_embedding_similarity.py` | existing — not yet verified |
| Graph projection + CTE store (`edges`) | `engine/graph/` | `test_graph_projection.py`, `test_graph_queries.py` | existing — not yet verified |
| PDF ingest with chain-of-custody | `services/document_ingest.py`, `services/document_jobs.py` | `test_document_ingest.py` | existing — not yet verified |
| Operational extraction + anomaly gate | `workflows/extract_ops.py` | — | existing — not yet verified |
| Hybrid retrieval (`hybrid_search`) + OKF bundles | `workflows/retrieval.py` | — | existing — not yet verified |
| Shared 35-rpm rate limiter | `services/rate_limit.py` | — | existing — not yet verified |
| SSE streaming | `workflows/base.py`, `frontend/src/lib/api.ts` | — | existing — not yet verified |
| Frontend pages: Home, Graph, Workflows, Connectors, Assets, Review queue, Documents | `frontend/src/pages/` | build + lint only | existing — not yet verified |
| Hidden (M-D1): Ask Copilot, RCA, Compliance | `workflows/chat.py`, `rca.py`, `compliance.py` | `test_chat_guard.py`, `test_chat_router.py`, `test_rca_calibration.py`, `test_workflows_rca_compliance.py` | hidden from nav and Workflows hub (M.0); routes unchanged |
| Docker images + deploy configs | `Dockerfile`, `Dockerfile.slim`, `render.yaml`, `railway.toml`, `deploy/`, `frontend/vercel.json` | — | config exists — no deployment verified |

Backend paths are under `backend/app/`, tests under `backend/tests/`.

---

## Project tasks (outside the M modules)

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| P.1 | Run the local stack and seed demo data (`demo/reset_and_seed.py`) | agent | 🔄 | Baseline (Task 0, `feat/atlogs-core`, Python 3.12 venv from `requirements-slim.txt` + pytest 8.3.4, no `DATABASE_URL`): `pytest` 36 passed / 7 skipped; `npm run build` passes (chunk >500 kB warning); `npm run lint` 8 errors (pre-existing, e.g. `react-hooks/set-state-in-effect` in `Documents.tsx`). Same counts after the Atlas→atlogs rename; sidebar wordmark checked in browser (`vite preview`). Kept as `atlas` on purpose (do not rename): `render.yaml` service `atlas-api` (renaming creates a new Render service); hosted URLs in `demo/seed_hosted.py` (live endpoints); localStorage keys `atlas.sidebar.collapsed`, `atlas.ingestJobId` (renaming drops saved UI state / resumable job); `dataset-final-atlas/` in `.gitignore`/`.dockerignore` (on-disk folder name). Documents folder input now defaults empty (was a personal path); unused `atlas-logo.png` removed; the text wordmark needs no design row (`docs/design.md` does not specify the logo). After this fix pass: `python -m pytest` 43 passed / 0 skipped (a `DATABASE_URL` in `backend/.env` is now present, so the 7 DB tests ran and passed); build passes; lint 8 errors (unchanged). `package-lock.json` is out of sync (`npm ci` fails; used `npm install`, lockfile not committed). Seeding not run: no DB. |
| P.2 | Branch discipline: `main` protected, `feat/*` branches, PRs | — | ⬜ | AGENTS.md §4 |
| P.3 | CI: `pytest` (pure tests) on GitHub Actions | — | ⬜ | No CI exists |
| P.4 | CI: `ruff` / `mypy` linting | — | ⬜ | Best-effort |
| P.5 | CI: `npm run build` + `npm run lint` | — | ⬜ | |
| P.6 | Apply the approved dark-theme re-skin (tokens in `design.md`; retire `ShaderBackground`) | — | ⬜ | `index.css` still on the earlier theme |
| P.7 | Deploy frontend, backend, database; verify a reachable URL | — | ⬜ | Only after M.1 (no auth today) |
| P.8 | API reference + ER diagram for the atlogs data model | — | ⬜ | Extend `architecture.md` / `memory.md` |
| P.9 | Mobile audit at 360px for engineer flows | — | ⬜ | Log upload, log review, equipment lookup |
| P.10 | Course deliverables: final report, deck, demo video | — | ⬜ | Anchored to evaluation results |

---

## Risk register

| Risk | Likelihood | Impact | Mitigation | Status |
|------|-----------|--------|-----------|--------|
| No auth on any endpoint today | High | High | M.1 before any deployment with real data | ⬜ Open |
| Extraction errors (abbreviations, negation, ambiguous IDs) | High | High | Rule-based + terminology table, `needs_review` flags, human review (M.3–M.5) | ⬜ Open |
| Too little labelled history to evaluate risk | High | Medium | Label scores *uncalibrated*; `insufficient_evidence` flag (M-D5) | ⬜ Open |
| Reviewed corrections vs immutable `raw_json` | Medium | Medium | Resolve M-Q1 before M.6 | ⬜ Open |
| Scanned / OCR-poor PDFs | Medium | Medium | Docling layout + text-only fallback | ⬜ Monitor |
| Entity-resolution ambiguity for equipment | Medium | Medium | Review queue + durable manual decisions | ⬜ Monitor |
| NIM 40-rpm cap | High | Low | 35-rpm bucket + caches; extraction and search work without the LLM | ⬜ Monitor |
| Schema applied by hand drifts from `schema.sql` | Medium | Medium | Additive changes only; note manual steps in each PR | ⬜ Monitor |
| Timeline slip | Medium | High | Follow spec §13 order; each M task ships working software | ⬜ Monitor |

---

## M — Maintenance-log modules

**Goal:** build atlogs as the system described in
[`maintenance_of_unstructured_logs_context.md`](../maintenance_of_unstructured_logs_context.md)
(spec). Rules for doing the work: [`AGENTS.md`](../AGENTS.md).
Status words follow AGENTS.md §8: ✅ only with test or demo evidence linked.

### Decisions

| ID | Decision | Why | Consequence |
|----|----------|-----|-------------|
| M-D1 | Compliance, Ask Copilot and RCA are hidden from the nav, not deleted | Not in spec; keep approved code working | Remove nav items in `AppShell.tsx`; routes, code, tests unchanged |
| M-D2 | Role-based access: `users` table, roles `engineer` / `manager` / `admin`, hashed passwords, signed token, role check per endpoint | Spec §4, §11 security | Uses stdlib `hashlib.scrypt` + `hmac` — no new dependency. Moves RBAC out of PRD §9 "Out of scope" |
| M-D3 | Extraction is rule-based first (patterns + terminology table + negation check); the LLM only fills fields rules left empty, when a key is set | Works offline, testable, gives real confidence and source spans | Extraction runs without NVIDIA; `extract_ops.py` anomaly gate stays as-is |
| M-D4 | Stay on PostgreSQL + pgvector; no Neo4j, FAISS or OR-Tools | One-database doctrine (rules §1.1); spec §7 "do not introduce every technology" | Relationships in `edges`, similarity via pgvector/FTS, scheduling via a small greedy checker |
| M-D5 | Risk = transparent weighted formula, labelled *uncalibrated* | Spec §5: evaluate before trusting | Formula + weights versioned in code and stored with each assessment |
| M-D6 (was M-Q1) | A reviewed record enters `source_records` once, on first approval; later corrections update `maintenance_records.reviewed` and the graph reads reviewed fields from there | `raw_json` immutable; avoids duplicate cases | No versioned rows in `source_records` |
| M-D7 (was M-Q2) | Notifications are in-app only, a derived query (no table) | Smallest working option | No email/SMTP config |
| M-D8 (was M-Q3) | Criticality, technicians and parts come from admin pages only; start empty | User decision | No resource seed JSON; demo data is entered through the UI/API |
| M-D9 (was M-Q4) | First admin is created by a one-off script reading `ADMIN_EMAIL` / `ADMIN_PASSWORD` from env | No hard-coded credentials | `backend/scripts/create_admin.py` |
| M-D10 | Test fixtures and the similar-case set use ~30 synthetic hand-written logs | No real logs available yet | Fixtures in `backend/tests/fixtures/`; re-evaluate when real data arrives |

### Open decisions

| ID | Question | Owner | Recommendation |
|----|----------|-------|----------------|
| — | None open | — | — |

### Data model (additive, in `backend/app/db/schema.sql`)

| Table | Key columns | Spec store |
|-------|-------------|-----------|
| `users` | email unique, password_hash, role, active | Users |
| `maintenance_logs` | sha256 (indexed, not unique: "submit anyway" adds a second row), filename, original_text, submitted_by, status (`received`/`extracted`/`reviewed`/`error`), error | Raw logs |
| `maintenance_records` | log_id FK, `extracted` jsonb (value, span, confidence, needs_review per field), `reviewed` jsonb, reviewed_by, reviewed_at, unified_id | Structured records |
| `terminology` | term, canonical, kind (component/symptom/action/abbrev) | Terminology |
| `risk_assessments` | record_id FK, score, category, factors jsonb, method_version, insufficient_evidence | Risk |
| `recommendations` | record_id FK, risk_id FK, priority, explanation jsonb, status (`pending`/`approved`/`modified`/`rejected`) | Recommendations |
| `technicians`, `parts` | skills[], availability windows; qty on hand | Resources |
| `schedule_proposals` | recommendation_id FK, assignments jsonb, conflicts jsonb | Schedules |
| `decision_audit` | recommendation_id FK, action, original jsonb, final jsonb, user_id, comment, created_at — append-only | Audit |

Equipment reuses `unified_assets` (+ a `criticality` column with a default). Logs flow
into the existing pipeline as `source_records` with `system = 'maintenance_logs'`, so
resolution, `edges` and `hybrid_search` work unchanged.

### Tasks

| # | Task | Spec | Depends | Owner | Status | Evidence |
|---|------|------|---------|-------|--------|----------|
| M.0 | Hide Ask, RCA, Compliance from nav (M-D1); README run/test instructions | §13.1 | — | — | 🔄 | Nav/hub hiding done: `npm run build` ok, lint 8 pre-existing errors (no new), pytest 43 passed (DB), browser: nav and Workflows hub hide Ask/RCA/Compliance, `/ask` and `/workflows/rca` still load. Remaining: README run/test instructions |
| M.1 | `users` table, password hashing, signed token, `require_role()` dependency on every route, login endpoint + page, admin user script | §4, §11, M-D2 | — | — | 🔄 | Backend: `services/auth.py`, login/me, `create_admin.py`, `users` table; router-level `require_role()` on every route except `/api/health` and login; admin-only: DELETE connectors, `documents/ingest-path`, `/api/admin/users` (list/create/set role+active). Frontend: `Login`, `RequireAuth` guard, admin `Users` page, Bearer header + 401 redirect in `lib/api.ts` (SSE already uses fetch streaming). Evidence: pytest 91 passed (41 new in `test_route_auth.py`, local DB); build ok; lint 8 pre-existing errors, none new; browser: login/logout as engineer, manager, admin, bad password, garbage token to /login, admin-only Users page and create user/set role. Not yet verified: `create_admin.py` (no `ADMIN_PASSWORD` in `.env`), UI hiding of admin-only buttons for non-admins (server enforces 403) |
| M.2 | Log ingestion: `POST /api/logs` (text or `.txt`/`.log`/`.csv` upload), size/type validation, sha256 duplicate warning with "submit anyway", original text preserved, status lifecycle; list + detail routes | M1 | M.1 | — | 🔄 | `maintenance_logs` table (applied by hand with psql); `services/logs.py`; `POST/GET /api/logs`, `GET /api/logs/{id}` (any signed-in role); 1 MB max, UTF-8 then Latin-1, 415 bad type, 400 empty, 413 oversize, 409 duplicate with `existing_id` unless `force=true`; original saved before `extract()` (placeholder until M.4; log stays `received`, extractor exception → `error` + message, text intact). `Logs` page + nav item. 30 synthetic fixtures in `backend/tests/fixtures/maintenance_logs.json` (M-D10). Evidence: pytest 107 passed / 0 skipped (16 new in `test_logs.py`, local DB); build ok; lint 8 pre-existing errors, none new; browser: paste submit, duplicate warning + "Submit anyway", PDF rejected with message. Not yet verified: file upload through the browser (only the rejected PDF path), 1 MB oversize in the browser (API test only), `extracted`/`reviewed` transitions (need M.4/M.5) |
| M.3 | Terminology table + seed (abbrevs like brg→bearing, vib→vibration) | M2 step 6 | — | — | 🔄 | `terminology` table + 22 seed rows (`on conflict do nothing`, applied by hand with psql); pure `knowledge/terminology.py` `normalise()` (case/punctuation-insensitive, unknown passes through; single-word terms only); admin-only `GET/PUT /api/admin/terminology`, `DELETE /api/admin/terminology/{term}`. Evidence: pytest 118 passed / 0 skipped (2 new normaliser tests, new routes covered by `test_route_auth.py`); build ok; lint 8 pre-existing errors, none new. Not yet verified: CRUD against the DB with an admin token (only 401/403 tested), no UI page |
| M.4 | Rule-based extractor: sentence split, equipment IDs (reuse `knowledge/patterns.py`), component/symptom/action/date/outcome, negation scope ("not replaced", "no leak found"), char spans, confidence, needs_review flag; optional LLM fill (M-D3) | M2 | M.3 | — | 🔄 | `engine/log_extract.py` (pure `extract(text, terminology)`): equipment via tag `P-104` + `patterns.py` ids, vocabulary + terminology-table matching, dates, negation within 3 tokens before a term (comma ends scope; negated hits listed in `negated`, never in fields). Field = `{value, span, confidence, needs_review (<0.75), source}`. `maintenance_records` table added (applied by hand with psql); `POST /api/logs` now writes `extracted` and sets status `extracted`. LLM fill (`logs.fill_with_llm`) only for empty fields, only with `NVIDIA_API_KEY`, via `resilient(get_extract_model())` (shared rate limiter), value must appear verbatim in the log, `source:'llm'`, `needs_review`. Limits: action value is the verb only; one value per field (best confidence, then earliest). Evidence: pytest 126 passed / 0 skipped (8 new in `test_log_extract.py`, local DB); build ok; lint 8 pre-existing errors. Not verified: LLM path with a real key |
| M.5 | Review API + "Log review" page: fields beside highlighted source text, correct/confirm, save to `reviewed` (extracted kept) | M2 steps 8-11 | M.2, M.4 | — | 🔄 | `PUT /api/records/{log_id}/review` (engineer, admin; manager gets 403) writes `reviewed` beside `extracted`, sets `reviewed_by`/`reviewed_at`, log status `reviewed`; unknown field 422, no record 404; `GET /api/logs/{id}` now includes `record`. Page `/logs/:id` (linked from Logs): source text with `<mark>` spans labelled by field name, `Needs review` text badge + `(needs review)` in the mark label (not colour-only), labelled inputs, keyboard-only save, read-only for managers. Evidence: pytest 128 passed / 0 skipped (1 new: correction persists, extracted and original unchanged, 401/403/422/404); build ok; lint 8 pre-existing errors, none new; browser (Playwright): engineer edit + clear field, keyboard Tab+Enter save, persists after reload, source text unchanged, needs-review labels shown, manager sees disabled inputs. Not verified: `reviewed` values are not yet consumed downstream (M.6); no re-review history (latest review overwrites `reviewed`) |
| M.6 | On review approval, push record into pipeline (`system='maintenance_logs'`), link equipment/component/symptom/action edges | M3 | M.5, M-Q1 | — | 🔄 | First review inserts `source_records` (`maintenance_logs:<log_id>`; raw_json = reviewed fields + `log_id` + pre-filled `_ext` + `_event_kind`, equipment stored as `asset_tag`) then runs `ingest_records({})`; later corrections only update `reviewed`, and every rebuild overlays the current reviewed values (`logs.projection_raw`), so `raw_json` is never rewritten. New relations `HAS_COMPONENT`, `EXHIBITED`, `ADDRESSED_BY` (+ node types component/symptom/action with colours); a missing link is skipped. `rebuild_operational_edges` now skips only the LLM path offline: records with `_ext` still get edges (dependency edges stay online-only); pre-filled `_ext` bypasses the extraction cache. Evidence: pytest 133 passed / 0 skipped (5 new in `test_log_graph.py`: edges created, registry asset reused, offline, first-approval-only, correction read on rebuild, missing links); build ok; lint 8 pre-existing errors, none new. Not verified: embeddings-on path (no NVIDIA key), browser view of the new node colours; a correction shows in the graph only at the next rebuild (no refresh on edit); if the graph update fails after first approval the review is kept and the API returns 502 until the next ingest |
| M.7 | Similar cases: `similar_cases(text, filters, k)` on FTS + pgvector fused with `_rrf_fuse`, restricted to `maintenance_logs`; filters equipment / component / date range; explicit "no relevant match" below threshold; panel in record view | M4 | M.6 | — | 🔄 | `retrieval.similar_cases`: FTS relevance = Dice word overlap of stemmed lexemes (`SIMILAR_MIN_FTS` 0.25), pgvector only when embeddings work (`SIMILAR_MIN_VECTOR` 0.62; embedding failure falls back to FTS-only); both thresholds *uncalibrated* (`shortcut:` comments). Filters read current values (reviewed, else extracted) from `maintenance_records`; date filters match ISO dates only. `GET /api/records/{log_id}/similar` (log itself excluded) and `POST /api/similar`, any signed-in role; each match has `log_id`, `link` (`/logs/<id>`), `citation`, scores, snippet. Panel "Similar past cases" on `/logs/:id`. Evidence: pytest 140 passed / 0 skipped (5 new on a 5-case labelled synthetic set: relevant above unrelated, filters, no-match reason, vector fused + fallback, routes/auth); build ok; lint 8 pre-existing errors, none new; browser (Playwright): panel lists the related log with a working link, shows "no relevant match" for an unrelated log. Not verified: live NVIDIA embeddings (no key), thresholds on real logs |
| M.8 | Equipment criticality + technicians + parts (admin pages, start empty, M-D8) | M6 | M.1, M-D8 | — | 🔄 | `tests/test_resources.py`: CRUD, 401/403 for engineer, criticality survives `rebuild_projection` with a changed `unified_id`. `asset_criticality` keyed by (concept, value) of the primary identifier. `PUT /api/assets/{id}/criticality`, `/api/resources/{technicians,parts}` (manager/admin), Resources page, selector on Assets. Browser-checked (manager) |
| M.9 | Risk baseline (M-D5): recurrence on same component, recent incidents, criticality, similar-case outcomes → score, category, factors, `insufficient_evidence` | M5 | M.7, M.8 | — | 🔄 | `engine/risk.py` pure `assess_risk(features)` → `{score, category, factors, insufficient_evidence, method_version='risk-v0-uncalibrated'}`: weights recurrence 30 (cap 3), recent incidents 20 (cap 5), criticality 25 (low 0/medium .5/high 1), similar-case adverse rate 25; category cut-offs 34/67; `insufficient_evidence` when <3 history records on the equipment or criticality unknown (score still shown, reasons listed). `services/risk.py` gathers inputs (same equipment ±90 days of the log date, else upload date; similar cases via `similar_cases`) and inserts into `risk_assessments` with `input_refs`. `POST/GET /api/records/{log_id}/risk` (any signed-in role); "Failure risk" panel on `/logs/:id` with an *Uncalibrated* badge and factor table. Weights, caps, cut-offs and the adverse-outcome keyword guess are uncalibrated (`shortcut:` comments). Evidence: pytest 162 passed / 0 skipped (7 new in `test_risk.py`, local DB); build ok; lint 8 pre-existing errors, none new. Not verified: browser (dev servers could not be started in this session), any comparison with real outcomes; the extractor only finds positive outcomes, so the similar-case adverse rate will mostly be 0 or no data |
| M.10 | Priority recommendation: documented policy from risk + stated urgency + criticality + recurrence, with explanation | M6 | M.9 | — | ⬜ | tests per factor |
| M.11 | Schedule proposal: greedy assignment honouring skills, availability, no double-booking, part stock; unschedulable → conflict flag, priority **not** lowered | M6 | M.8, M.10 | — | ⬜ | conflict, missing skill, missing part tests |
| M.12 | Decisions: approve/modify/reject (manager role), append to `decision_audit` with original vs final, user, timestamp, comment; history view | M8 | M.10, M.11 | — | ⬜ | tests: original preserved after modify; engineer denied |
| M.13 | Dashboard + notifications: Home shows log status, pending review, high-priority, unschedulable, recent decisions (M-Q2) | M7 | M.5, M.12 | — | ⬜ | browser check per role |
| M.14 | End-to-end test of spec §6 example; update `prd.md`, `architecture.md`, `memory.md`, `rules.md` | §14, §16 | all | — | ⬜ | e2e test output |

Order follows spec §13; M.3/M.4 can run in parallel with M.1/M.2, and M.8 in parallel
with M.6/M.7.
