# atlogs — Development Rules & Conventions

> Mandatory rules for all contributors. Process rules (branches, testing, status
> words) are in [`AGENTS.md`](../AGENTS.md); this file holds the system invariants.
> All rules below describe code that exists on `feat/atlogs-core`; where a rule is
> not enforced by a test, the section says so.

---

## 1. Architecture Rules

### 1.1 One database

- **All** storage lives in PostgreSQL + pgvector: logs, records, vectors, FTS,
  relationships, resources, assessments, audit.
- Graph traversal uses recursive CTEs over `edges`.
- No Neo4j, FAISS, Qdrant, Pinecone, ElasticSearch, or Redis for data (M-D4).
- Scheduling uses a small greedy checker in Python, not OR-Tools (M-D4).
- A second datastore or solver needs a decision entry first (§10).

### 1.2 Single worker

- The backend runs as a **single uvicorn worker**; the in-memory job registry
  and asyncpg pool assume one process.
- Never add `--workers`, `--processes`, or extra replicas without a decision.

### 1.3 Controlled workflows, not free agents

- LLM workflows are LangGraph state machines with a fixed call budget.
- Deterministic guards run before any model call; the model is skipped when
  evidence doesn't exist.

### 1.4 Human-controlled decisions

- The system **recommends**; a manager approves, modifies, or rejects.
- No code path approves a recommendation, confirms a schedule, or triggers an
  action automatically.

---

## 2. Data Integrity Rules

### 2.1 Originals are immutable

- `source_records.raw_json` is never modified after storage.
- `maintenance_logs.original_text` is never modified; cleaning and
  normalisation work on copies.
- Derived data (assets, edges, OKF bundles) can be rebuilt from raw records.

### 2.2 Reviewed beside extracted 

- `maintenance_records.extracted` is written once by the extractor.
- Human corrections go to `maintenance_records.reviewed`, with `reviewed_by` and
  `reviewed_at`. Never overwrite extracted values.

### 2.3 Append-only audit

- `decision_audit` rows are insert-only: no `UPDATE`, no `DELETE`.
- A "modify" decision stores both `original` and `final`; the original
  recommendation is never overwritten.
- `risk_assessments` are insert-only; a re-assessment is a new row.

### 2.4 Status never lies

- A failed upload or extraction ends in `status = 'error'` with the original
  kept, never in a state that looks complete.
- PDF chain-of-custody: `parse → DURABLE SAVE → extract → resolve`. Failure
  before save persists nothing; failure after save keeps the parse with
  `status=error`. A source document is never silently lost.

### 2.5 Incremental + accumulative ingestion

- Only new `(system, record_id)` pairs are stored.
- Re-resolution runs over the whole corpus; one source never clobbers another.
- Deleting a connector drops that system's records and re-resolves the rest.

### 2.6 Deduplication

- Records: `UNIQUE (system, record_id)`.
- Documents: `UNIQUE (sha256)`; re-uploading an identical file is a no-op.
- Logs: `sha256` is indexed, **not** unique. A duplicate returns 409 with `existing_id`;
  `force=true` ("submit anyway") stores a second row.
- OKF bundles: re-embed only when `body_hash` changes.

### 2.7 Schema changes are additive

- `create table if not exists`, new columns with defaults. `schema.sql` is
  applied by hand; note any manual migration step in the PR.

---

## 3. Extraction, LLM & AI Rules

### 3.1 Rule-based extraction first (M-D3)

- Extraction runs on patterns, the terminology table and a negation check, with
  char spans, a confidence value and `needs_review` per field.
- It must work with no NVIDIA key. The LLM only fills fields rules left empty.
- Negation is respected: "not replaced" is not a replacement; "no leak found"
  is not a leak.
- Equipment IDs reuse `knowledge/patterns.py`.

### 3.2 Rate budget

- One shared token bucket: 35 rpm steady, burst 5, fronting **all** NVIDIA calls
  (embeddings, chat, rerank, extraction). NIM free tier = 40 rpm.
- Every NVIDIA call goes through the shared limiter and the `resilient()` retry
  wrapper.

### 3.3 Model tiers

| Tier | Model | When to use |
|------|-------|-------------|
| Reasoning | `nemotron-3-ultra-550b-a55b` | Streamed chat answers (hidden feature) |
| Fast | `nvidia-nemotron-nano-9b-v2` | Routing, JSON classification, structured output |
| Extract | Nano, "detailed thinking off" | High-volume extraction, optional field fill |
| Rerank | `llama-nemotron-rerank-1b-v2` | Cross-encoder rerank |
| Embed | `nemotron-3-embed-1b` | 2048-d embeddings |

Never use the reasoning tier for routing, classification or extraction.

### 3.4 Grounding

- Identifiers are validated by standards-derived regexes before anchoring.
- Every extracted field, similar case and recommendation links back to its
  source log or record.
- Citations are checked to exist; contradictions are shown, never hidden.

### 3.5 Anomaly gating

- Deterministic vocabulary first; LLM `is_anomaly` is only a tie-breaker.
- "Completed successfully" / "no action required" never becomes a failure.

---

## 4. Scoring & Confidence Rules

### 4.1 Risk and priority *(M-D5)*

- Risk is a transparent weighted formula in Python; weights and
  `method_version` live in code and are stored with each assessment.
- Every score shows its factors; missing data sets `insufficient_evidence`.
- Risk scores are labelled ***uncalibrated*** in the API and UI until evaluated
  against labelled outcomes (spec §5).
- **Priority policy** (`engine/priority.py`, `priority-v0`, uncalibrated): points are summed
  and cut into P1-P4; every recommendation is stored `pending` with its factor list
  (`factor`, `input`, `points`, `reason`).

  | Factor | Points |
  |--------|--------|
  | Risk category (from the latest assessment) | low 0, medium 2, high 4 |
  | Stated urgency: `urgent`/`urgently`, `immediate`/`immediately`, `shutdown`/`shut-down` | +3, once |
  | Equipment criticality | unknown/low 0, medium 1, high 2 |
  | Recurrence on the same component, 90 days | 0 → 0, 1 → 1, 2 or more → 2 |

  Cut-offs: total ≥ 8 → **P1**, ≥ 5 → **P2**, ≥ 2 → **P3**, else **P4**.
  An urgency word after a negator (`not urgent`, `no shutdown needed`) is
  detected with the extractor's negation rule (`log_extract._negated`) and does **not** raise
  priority; the explanation says it was ignored. Points and cut-offs are guesses until
  compared with managers' decisions.
- An unschedulable task is flagged as a conflict (`skill`, `part` or `availability`); its priority is **not** lowered.
  Scheduling (`engine/schedule.py`, pure, greedy) takes pending recommendations in priority order
  (P1 first, then id), gives each the earliest slot of a free technician with the required skill, and
  uses up one unit per listed part within the proposal only. Skill, duration and parts per component
  come from the manager-editable `component_defaults` table; unknown components need skill `general`
  for 60 min. A proposal books nothing, part stock is never written back, and a decision does not confirm it (not built).
- No LLM computes risk, priority, schedules or decisions.

### 4.2 Resolution confidence (existing)

```
confidence = min(1.0, base × redundancy × conflict_penalty)
```

- `redundancy_bonus` = 1.0 / 1.05 / 1.08 (+0.03 for anchor+embedding)
- `conflict_penalty` = 0.40 (strong ID clash) / 0.80 (medium)

Never change these or the merge bands without a decision entry and updated
tests in `test_resolution.py`.

### 4.3 RCA confidence cap (existing, hidden feature)

```
cap = 0.45 + 0.25·grounded + 0.20·upstream + 0.05·corroborated − 0.08·contradictions
clamp [0.10, 0.98]; ungrounded ≤ 0.40
```

### 4.4 Deterministic where it matters

Always computed in SQL/Python, never by a model: risk score, priority, schedule
feasibility, compliance at-risk list, overview counts, answer confidence, RCA
calibration, anomaly gating (primary signal).

---

## 5. API & Backend Rules

### 5.1 Access control (M-D2)

- Every endpoint depends on `require_role()`; no route is public except
  `GET /api/health` and login.
- Passwords hashed with stdlib `hashlib.scrypt`; tokens HMAC-signed, 8 h expiry; the API refuses to start without `AUTH_SECRET`.
- Roles: `engineer`, `manager`, `admin`. `manager`/`admin` decide on
  recommendations, schedule, manage resources and criticality and read the audit;
  only `admin` manages users, terminology and connector deletion; only `engineer`/`admin` edit review fields.
- Not covered: login rate limiting, token revocation, password reset.
- No default hard-coded password; the first admin comes from a script reading
  env (M-D9, `backend/scripts/create_admin.py`).
- Routes are checked by `test_route_auth.py` (401 without a token, 403 for the wrong role).

### 5.2 Validation at the boundary

- The backend owns validation, permissions and database writes; the frontend
  only presents and submits.
- Log uploads check type (`.txt`/`.log`/`.csv` or text) and size
  before anything is stored.

### 5.3 Streaming

- Long actions stream status via SSE; navigating away never kills a job;
  clients support reconnect-safe replay + heartbeat.

### 5.4 Error handling

- Embedding failure → resolution degrades to exact-identifier matching.
- Docling failure → pypdfium2 text-only fallback.
- LLM 429 → bounded exponential backoff (`resilient()`).
- No LLM key → extraction and search still work (rules / FTS).
- Empty corpus → wipe all derived state cleanly.

### 5.5 Caching

Check the cache before any NIM call: record embeddings (`source_records.id`),
document extractions (`sha256`), operational extractions (`record_id`), OKF
bundles (`body_hash`).

---

## 6. Frontend Rules

- Colours, fonts, radii and spacing come from CSS custom properties in
  `index.css`; never hardcode values in components.
- Use shadcn/ui primitives from `components/ui/`; no parallel component library.
- SSE uses `lib/api.ts` helpers; don't roll custom SSE parsing.
- Types mirror backend payloads in `lib/types.ts`.
- Risk is always shown with its *uncalibrated* label and factors; an estimate is
  never styled as a confirmed failure.
- Hidden features (Ask, RCA, Compliance) stay routable but off the nav (M-D1).
- Accessibility: respect `prefers-reduced-motion`; keyboard-navigable controls;
  status never colour-only; descriptive IDs on interactive elements.

---

## 7. Testing Rules

- Existing coverage to keep green: `test_resolution.py`,
  `test_document_ingest.py`, `test_rca_calibration.py`, `test_chat_guard.py`,
  `test_chat_router.py`, `test_graph_*`, `test_schema_discovery.py`,
  `test_embedding_similarity.py`, `test_workflows_rca_compliance.py`.
- New non-trivial logic ships with tests: extraction + negation, normaliser,
  risk formula (incl. missing data), priority factors, scheduler conflicts,
  role denials, audit preservation (see each M task's Evidence column).
- `test_e2e_spec6.py` walks spec §6 (upload → extract → review → graph → similar → risk → priority → schedule → decision → audit). It runs offline and only against a `localhost`/`127.0.0.1` `DATABASE_URL`; otherwise it skips.
- DB-integration tests **skip** (not fail) without Postgres.
- Formula changes require matching test updates.

---

## 8. Git & Branch Rules

See [`AGENTS.md`](../AGENTS.md) §4: `feat/*` branches, PRs to `main`, stage by
name, never commit `.env` or keys, no force push.

---

## 9. Deployment Rules

- Backend image ≤ 512 MB on free-tier hosts: `Dockerfile.slim` with
  `DOCLING_ENABLED=false`. Full Docling needs ≥ 2 GB RAM.
- `FRONTEND_ORIGIN` must be set on the backend for CORS.
- Health check: `GET /api/health` (live DB query).
- Supabase free tier pauses after ~7 days idle.
- Don't call anything deployed without a checked URL (AGENTS.md §8).

---

## 10. Decision Log Protocol

The **Decisions** table in [`tasks.md`](tasks.md) (section "M — Maintenance-log
modules") is the decision log. Unresolved questions go in its **Open decisions**
table with an owner.

A decision entry (ID, decision, why, consequence) is required before:

1. Adding a second datastore, vector index or solver
2. Changing confidence formulas, merge bands, or the risk/priority formula
3. Adding free-roaming agent behaviour or any automatic approval/action
4. Introducing a new LLM model tier or a new dependency
5. Changing the rate budget or caching strategy
6. Modifying the chain-of-custody boundary or the immutability/audit rules
7. Adding horizontal scaling (multi-worker/replica)
8. Changing roles or permissions
