# atlogs — Product Requirements Document (PRD)

> **Course:** UCS503P Software Engineering Project, Thapar Institute
> Target behaviour: [`maintenance_of_unstructured_logs_context.md`](../maintenance_of_unstructured_logs_context.md) (spec).
> The maintenance modules below are implemented on branch `feat/atlogs-core`
> (not merged, not deployed). Verification status and evidence per task:
> [`tasks.md`](tasks.md). Spec §6 end to end: `backend/tests/test_e2e_spec6.py`.
> Risk and priority numbers are *uncalibrated* baselines (M-D5).

---

## 1. Summary

**atlogs** is an AI-assisted maintenance decision-support system. It accepts
free-text maintenance logs, extracts structured fields, lets engineers review
them, links equipment, components, symptoms and actions, retrieves similar
historical cases, and produces an explainable risk indicator, priority
recommendation and resource-aware schedule proposal. A responsible person
approves, modifies or rejects every recommendation, and the decision is audited.

The existing ingestion, entity resolution, graph and retrieval layers are
reused as the foundation (§4.10).

## 2. Problem (spec §2)

Maintenance information is written as free text. The same symptom is described
with different words and abbreviations ("motor overheated", "excessive
temperature in motor assembly"), so keyword search misses related cases.

1. Important fields are buried in paragraphs.
2. Finding useful historical cases means reading many old records.
3. Recurring issues hide behind different terminology.
4. Urgency is hard to compare across requests.
5. Urgent work may need a technician, part or slot that is unavailable.
6. Users need to see why something was recommended and what was decided.

## 3. Users (spec §4)

| Role | Key needs |
|------|-----------|
| **Maintenance Engineer** (`engineer`) | Upload logs, review and correct extracted fields, search similar cases, read risk and priority |
| **Maintenance Manager** (`manager`) | Review recommendations and evidence, approve / modify / reject, review resources and schedules, monitor status and decision history |
| **System Administrator** (`admin`) | Manage users and roles, maintain configuration, equipment criticality and resources |

---

## 4. Functional Requirements

Grouped by spec module. FR numbers map to spec §10 items in brackets.

### 4.1 Access control (spec §4, §11; decision M-D2)

| ID | Requirement | Priority |
|----|------------|----------|
| FR-01 | Users sign in with email + password; passwords stored hashed (`hashlib.scrypt`) | Must |
| FR-02 | Signed (HMAC) session token; expired or forged tokens rejected | Must |
| FR-03 | Every API endpoint checks the caller's role (`engineer` / `manager` / `admin`) | Must |
| FR-04 | Admin manages user accounts and roles | Must |

### 4.2 M1 — Log input and storage [1, 2]

| ID | Requirement | Priority |
|----|------------|----------|
| FR-10 | Accept log text or a `.txt` / `.log` / `.csv` file; reject unsupported type or size with a clear error | Must |
| FR-11 | Detect duplicates by SHA-256; warn and let the user submit anyway | Must |
| FR-12 | Assign a unique ID and preserve the original text unchanged | Must |
| FR-13 | Track processing status (`received` → `extracted` → `reviewed`, or `error`); a failure never leaves a record that looks complete | Must |

### 4.3 M2 — Information extraction and review [3, 4, 5] (decision M-D3)

| ID | Requirement | Priority |
|----|------------|----------|
| FR-20 | Rule-based extraction of equipment, component, symptom, action, date, outcome, failure terms; works without an LLM key | Must |
| FR-21 | Negation-aware: "the bearing was not replaced", "no leak found" are not read as a replacement or a leak | Must |
| FR-22 | Each field carries its source span, a confidence value and a `needs_review` flag | Must |
| FR-23 | Normalise terms through a terminology table (abbreviations, synonyms) | Must |
| FR-24 | Optional LLM fill for fields rules left empty, only when an NVIDIA key is set | Should |
| FR-25 | Review screen shows fields beside highlighted source text; user corrects or confirms | Must |
| FR-26 | Reviewed values are stored beside extracted values, never over them | Must |

### 4.4 M3 — Knowledge representation [6] (decision M-D4)

| ID | Requirement | Priority |
|----|------------|----------|
| FR-30 | A reviewed record links equipment → component → symptom → action → case in the existing `edges` table | Must |
| FR-31 | Existing equipment entities are reused via entity resolution | Must |
| FR-32 | Update failures never silently drop existing relationships | Must |

### 4.5 M4 — Historical case retrieval [7]

| ID | Requirement | Priority |
|----|------------|----------|
| FR-40 | Find similar cases from a selected record or free text, using pgvector + FTS (`hybrid_search`) | Must |
| FR-41 | Filter by equipment, component and date range | Must |
| FR-42 | Report "no relevant match" clearly below a threshold | Must |
| FR-43 | Every result links to its source log | Must |
| FR-44 | Search works without an LLM key (FTS-only path) | Should |

### 4.6 M5 — Failure-risk assessment [8] (decision M-D5)

| ID | Requirement | Priority |
|----|------------|----------|
| FR-50 | Transparent weighted formula over recurrence on the same component, recent incidents, criticality and similar-case outcomes | Must |
| FR-51 | Output score, category and contributing factors; flag `insufficient_evidence` | Must |
| FR-52 | Store each assessment with timestamp, inputs and method version | Must |
| FR-53 | Label scores *uncalibrated* until evaluated against labelled outcomes | Must |

### 4.7 M6 — Priority and scheduling [9, 10, 12]

| ID | Requirement | Priority |
|----|------------|----------|
| FR-60 | Recommend a priority from risk, stated urgency, criticality and recurrence, with an explanation | Must |
| FR-61 | Model technicians (skills, availability) and parts (stock); equipment criticality | Must |
| FR-62 | Propose a schedule (greedy checker): honour skills and availability, no double-booking, part stock | Must |
| FR-63 | An unschedulable task is flagged as a conflict; its priority is **not** lowered | Must |

### 4.8 M7 — Dashboard and notifications [13]

| ID | Requirement | Priority |
|----|------------|----------|
| FR-70 | Dashboard shows log status, pending review, high-priority and unschedulable items, recent decisions, filtered by role | Must |
| FR-71 | In-app notifications derived from clear conditions (pending review, high priority, unschedulable); delivery channel is open decision M-Q2 | Should |

### 4.9 M8 — Decisions and audit [11, 14]

| ID | Requirement | Priority |
|----|------------|----------|
| FR-80 | A manager approves, modifies or rejects a recommendation; engineers cannot | Must |
| FR-81 | Append-only audit: original vs final, user, timestamp, comment, evidence | Must |
| FR-82 | Decision history is viewable, subject to role | Must |
| FR-83 | The system never approves or acts automatically | Must |

### 4.10 Existing foundation (kept)

| ID | Requirement | Priority |
|----|------------|----------|
| FR-90 | JSON connectors / `POST /api/ingest` as an additional input; dedupe by `(system, record_id)`; incremental, accumulative sync | Must |
| FR-91 | PDF ingestion with chain-of-custody (`document_parses` saved before extraction), text-only fallback without Docling | Should |
| FR-92 | Entity resolution with explainable confidence, merge bands, conflict penalty, review queue and durable manual decisions | Must |
| FR-93 | Anomaly gate: benign logs ("completed", "no action required") never become failures | Must |
| FR-94 | Hybrid retrieval: dense + FTS + OKF dense, RRF (k=60), optional rerank | Must |
| FR-95 | 3D graph view with node inspector | Should |
| FR-96 | Long actions stream status over SSE | Should |

### 4.11 Hidden features (decision M-D1)

Ask Copilot (chat), Root Cause Analysis and Compliance are retained and hidden
from navigation. Their code, routes (`/api/chat`,
`/api/rca`, `/api/compliance`, `/api/graph/rca`, `/api/graph/compliance`) and
tests stay working, but they are not atlogs requirements.

---

## 5. Non-Functional Requirements (spec §11)

| ID | Requirement | Target |
|----|------------|--------|
| NFR-01 | Security: users reach only operations their role permits | Role check on every endpoint |
| NFR-02 | Traceability: structured records, assessments and decisions link to the source log | 100% of records |
| NFR-03 | Data integrity: original logs, `raw_json` and audit rows are never overwritten | Enforced in code + tests |
| NFR-04 | Robustness / error reporting: malformed input and failed processing give a clear error, no silent corruption | Tested per module |
| NFR-05 | Explainability: risk and priority show factors and evidence | Every recommendation |
| NFR-06 | Usability: review and recommendations understandable without training | TBD — to be defined and tested |
| NFR-07 | Modularity / maintainability: extraction, retrieval, risk, scheduling and UI are separate modules | — |
| NFR-08 | Privacy: operational data protected per deployment needs | TBD — to be defined and tested |
| NFR-09 | Response time, availability, extraction accuracy | TBD — to be defined and tested |
| NFR-10 | NVIDIA API rate budget | ≤ 35 rpm sustained (shared limiter, enforced) |
| NFR-11 | Works offline for extraction and search | No LLM key required |

---

## 6. Constraints

| Constraint | Details |
|-----------|---------|
| One database | PostgreSQL + pgvector only — no Neo4j, FAISS, Qdrant (M-D4) |
| Single worker | In-memory job registry + DB pool assume one process |
| NVIDIA NIM budget | Free tier 40 rpm shared by all LLM, embedding and rerank calls; limiter set to 35 |
| Human-controlled decisions | The system recommends; a manager decides |
| No new dependencies without a decision | Stdlib first; any new package is pinned and logged in tasks.md |
| No client-side secrets | All keys server-side |

---

## 7. Evaluation (spec §14)

| Area | What is tested |
|------|----------------|
| Log ingestion | Valid input accepted; invalid type rejected; duplicate warned; original retrievable; failed upload not shown as complete |
| Extraction | Equipment IDs, symptoms, actions; missing fields; negation; source spans shown; corrections persist |
| Retrieval | Relevant cases above unrelated ones on a small labelled set; filters; no-match message; links to source |
| Risk and priority | Expected inputs used; missing data explicit; explanation matches the formula; estimate shown as estimate; evaluated against labelled outcomes where available |
| Scheduling | No double-booking; skills and parts checked; infeasible reported; human approval kept |
| Audit and security | Approve / modify / reject recorded; original vs revised distinguishable; user + timestamp; role denials; failed operations don't corrupt records |
| End to end | Spec §6 example (Pump P-104) through the whole flow: `test_e2e_spec6.py` (needs a local database; skips otherwise). Not covered: browser flow, live NVIDIA embeddings, real logs |

The existing `backend/eval_suite.py` (resolution F1, anomaly gating, grounding,
calibration, leakage, compliance determinism) still runs; its chat/RCA/compliance
parts cover hidden features only.

---

## 8. Tech Stack (actual)

| Layer | Choice |
|-------|--------|
| Database | PostgreSQL + pgvector + tsvector FTS (Supabase); schema in `backend/app/db/schema.sql`, applied by hand |
| Backend | Python 3.12+, FastAPI (async), SSE, asyncpg |
| LLM / embeddings | NVIDIA NIM (Nemotron family) via LangChain; optional for extraction |
| Orchestration | LangGraph (existing workflows) |
| Documents | Docling, pypdfium2 fallback |
| Frontend | Vite + React 19 + TypeScript, Tailwind CSS v4, shadcn/ui, d3-force-3d |
| Auth | stdlib `hashlib.scrypt` + `hmac` — no new dependency |

---

## 9. Out of Scope

- Operating machinery or acting without human approval
- Real-time sensor streaming (batch input only)
- Multi-tenant isolation
- Custom LLM fine-tuning
- Native mobile apps (responsive web only)
- Multi-language / i18n
- Email or external notification delivery, (notifications are in-app only, M-D7)
