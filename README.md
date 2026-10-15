# atlogs

atlogs ("Maintenance of Unstructured Logs") is an AI-assisted maintenance
decision-support system. It turns free-text maintenance logs into structured,
searchable records and uses them to help engineers find similar past cases,
assess risk, prioritise work and plan maintenance. It recommends; a human decides.

Course: UCS503P Software Engineering Project, Thapar Institute.

## Status
The maintenance-log modules are implemented on branch `feat/atlogs-core` (local,
not merged, not deployed): login and roles, log upload, rule-based extraction,
log review, graph linking, similar cases, risk (uncalibrated), priority,
schedule proposal, manager decisions with an append-only audit, dashboard and
notifications. Ask Copilot, RCA and Compliance are hidden from the navigation but
still work. Per-task status and evidence: [`docs/tasks.md`](docs/tasks.md).

## Run locally
Needs Python 3.12+, Node.js, and a PostgreSQL database with the `pgvector`
extension.
1. Database: apply the schema by hand (nothing else applies it; it is additive and re-runnable):
   ```bash
   psql "$DATABASE_URL" -f backend/app/db/schema.sql
   ```
2. Backend environment: `cp backend/.env.example backend/.env` and set
   `DATABASE_URL`, `AUTH_SECRET` (signs login tokens; the API will not start
   without it), `ADMIN_EMAIL` and `ADMIN_PASSWORD` (read once by the next step).
   `NVIDIA_API_KEY` is optional: extraction, search and scoring work without it.
3. Backend (port 8000, single worker):
   ```bash
   cd backend
   python -m venv .venv && . .venv/bin/activate
   pip install -r requirements.txt        # or requirements-slim.txt (no Docling, no pytest)
   python scripts/create_admin.py         # creates the first admin from ADMIN_EMAIL / ADMIN_PASSWORD
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
   ```
   `GET /api/health` checks the live database connection.
4. Frontend (port 5173). The frontend defaults to port 8001, so set the URL:
   ```bash
   cd frontend
   npm install
   cp .env.example .env                   # then set VITE_API_URL=http://localhost:8000
   npm run dev
   ```
   Sign in with the admin account, then add engineer and manager users on the Users page.
   Technicians, parts and equipment criticality start empty and are entered on the
   Resources and Assets pages.
5. Optional demo data for the foundation (wipes all app tables; backend running,
   point it at your port): `python demo/reset_and_seed.py`. Walkthrough:
   [`demo/DEMO_SCRIPT.md`](demo/DEMO_SCRIPT.md).

## Test
```bash
cd backend && pytest                      # DB tests skip without DATABASE_URL
cd frontend && npm run build && npm run lint
```
`tests/test_e2e_spec6.py` walks the spec §6 P-104 example through the API and
runs only when `DATABASE_URL` points at `localhost` or `127.0.0.1` (it creates
and deletes its own rows, and rebuilds derived graph state). Frontend lint
currently reports 8 errors that predate the maintenance work. There are no
frontend tests and no CI yet.

## Docs
- Target behaviour: [`maintenance_of_unstructured_logs_context.md`](maintenance_of_unstructured_logs_context.md)
- Working rules: [`AGENTS.md`](AGENTS.md)
- Requirements: [`docs/prd.md`](docs/prd.md) · Architecture: [`docs/architecture.md`](docs/architecture.md)
- Data: [`docs/memory.md`](docs/memory.md) · Rules: [`docs/rules.md`](docs/rules.md) · UI: [`docs/design.md`](docs/design.md)
- Tracker and decisions: [`docs/tasks.md`](docs/tasks.md)

Docker images (`Dockerfile`, `Dockerfile.slim`) and deploy configs (`render.yaml`,
`railway.toml`, `deploy/`, `frontend/vercel.json`) exist; no deployment has been
verified for atlogs.
