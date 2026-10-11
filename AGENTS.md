# AGENTS.md — Working rules for humans and AI agents

This repo is **atlogs**, the **Maintenance of Unstructured Logs** decision-support
system.

- Target behaviour: [`maintenance_of_unstructured_logs_context.md`](maintenance_of_unstructured_logs_context.md)
- Work plan, owners, decisions: [`docs/tasks.md`](docs/tasks.md) → section "M — Maintenance-log modules"
- Existing invariants (one database, single worker, custody, rate budget): [`docs/rules.md`](docs/rules.md)
- System shape: [`docs/architecture.md`](docs/architecture.md), [`docs/memory.md`](docs/memory.md), UI: [`docs/design.md`](docs/design.md)

## 1. Read before editing

- Read the code you will touch, its callers, and its tests before changing it.
- Read the relevant module section of the context spec and the matching task row in `docs/tasks.md`.
- Key entry points: `backend/app/api/routes.py` (all routes), `backend/app/db/schema.sql`
  (all tables, applied by hand), `backend/app/services/pipeline.py` (ingest),
  `backend/app/workflows/extract_ops.py` (extraction), `backend/app/workflows/retrieval.py`
  (search, run history), `frontend/src/App.tsx` + `components/AppShell.tsx` (routes, nav).
- If code and docs disagree, trust the code, then fix the doc in the same change.

## 2. Make minimal changes

- Reuse what exists: `source_records`, `edges`, `hybrid_search`, `_anomaly_signal`,
  the rate limiter, SSE helpers in `lib/api.ts`, shadcn primitives in `components/ui/`.
- Standard library before a new dependency. A new dependency needs a pinned version
  and a line in the decisions table in `docs/tasks.md`.
- No speculative abstractions, config flags, or "for later" scaffolding.
- Schema changes are additive (`create table if not exists`, new columns with defaults).

## 3. Preserve existing behaviour

- Approved designs and feature contracts (API payloads, confidence formulas, merge bands,
  custody boundary, design tokens) do not change without written authorization in
  `docs/tasks.md` decisions.
- Compliance, Ask Copilot and RCA are **hidden from navigation, not deleted** (decision M-D1).
  Their code, routes and tests stay working.
- Original logs and `source_records.raw_json` are never modified. Reviewed values are
  stored beside extracted values, never over them. Audit rows are append-only.
- The system recommends; a human approves. Never add automatic approval or actions.

## 4. Protect Git history and local work

- Start with `git status` and `git diff`. Do not overwrite or revert changes you did not make.
- Work on `feat/*` branches; `main` takes PRs only.
- Stage files by name. Check `git diff --staged` before every commit. Never `git add -A` blindly.
- Never commit `.env`, keys, tokens, or test artifacts (screenshots, traces, dumps).
- No force push, `reset --hard`, `clean -f`, `--amend` on pushed commits, or `--no-verify`
  without the owner's explicit permission.

## 5. Test before declaring completion

Run what applies and report the **actual** output (pass/fail/skip counts), not expectations:

```bash
cd backend && pytest                          # DB tests skip without DATABASE_URL
cd frontend && npm run build && npm run lint
```

- New non-trivial logic (parsers, negation, scoring, scheduling, permission checks) ships
  with a test. Bug fixes ship with a test that failed before the fix.
- UI changes are checked in a browser (Playwright CLI), artifacts kept out of Git.
- If a check could not run (no DB, no API key), say so and say what remains unverified.

## 6. Coordinate shared work

- `docs/tasks.md` is the single tracker. Before starting a task, set its Owner and status 🔄;
  check its `Depends` column first.
- One owner per task. Touching another owner's open task needs their agreement.
- Unresolved questions go in the "Open decisions" table with an owner — never decide them
  silently in code.
- Hand-offs state: what changed, what was tested, what is left.

## 7. Keep documentation authoritative

- Update the existing doc that owns a topic: requirements → `docs/prd.md`, structure →
  `docs/architecture.md`, data → `docs/memory.md`, rules → `docs/rules.md`,
  status/decisions → `docs/tasks.md`, run instructions → `README.md`.
- Do not create new docs for notes, summaries, or plans. Update the owner doc in the same PR
  as the code.

## 8. Distinguish implementation from publication

- Status words mean: **implemented** = code merged + tests pass; **verified** = behaviour
  demonstrated (test or browser) with evidence linked in `docs/tasks.md`; **deployed /
  released** = a reachable URL or tag that you checked.
- Never claim deployed, released, or published without that evidence. "Merged to a branch"
  is not "released".
- Risk scores are labelled *uncalibrated* until evaluated against labelled outcomes (spec §5).
