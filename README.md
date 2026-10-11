# atlogs

atlogs ("Maintenance of Unstructured Logs") is an AI-assisted maintenance
decision-support system. It turns free-text maintenance logs into structured,
searchable records and uses them to help engineers find similar past cases,
assess risk, prioritise work and plan maintenance. It recommends; a human decides.

Course: UCS503P Software Engineering Project, Thapar Institute.

## Status

Early. The foundation (ingestion, entity resolution, knowledge graph, hybrid
search, PDF custody, 3D graph view) exists in the code. The maintenance-log
modules (login/roles, log upload, extraction review, similar
cases, risk, priority, scheduling, audit) are **planned**. See
[`docs/tasks.md`](docs/tasks.md) for what exists, what is planned and who owns it.

## Run locally

Needs Python 3.13, Node.js, and a PostgreSQL database with the `pgvector`
extension (e.g. Supabase).

1. Database: apply the schema by hand (no code applies it):

   ```bash
   psql "$DATABASE_URL" -f backend/app/db/schema.sql
   ```

2. Backend (port 8001, single worker):

   ```bash
   cd backend
   python -m venv .venv && . .venv/bin/activate
   pip install -r requirements.txt        # or requirements-slim.txt (no Docling, no pytest)
   cp .env.example .env                   # set DATABASE_URL, NVIDIA_API_KEY, FRONTEND_ORIGIN, ...
   uvicorn app.main:app --host 127.0.0.1 --port 8001 --workers 1
   ```

   `GET /api/health` checks the live database connection.

3. Frontend (port 5173):

   ```bash
   cd frontend
   npm install
   cp .env.example .env                   # VITE_API_URL, defaults to http://localhost:8001
   npm run dev
   ```

4. Optional demo data (wipes all app tables, then seeds the demo corpus; backend
   must be running on :8001):

   ```bash
   python demo/reset_and_seed.py          # --reset-only, --pdf <file-or-folder>
   ```

   Walkthrough: [`demo/DEMO_SCRIPT.md`](demo/DEMO_SCRIPT.md).

## Test

```bash
cd backend && pytest                      # DB tests skip without DATABASE_URL
cd frontend && npm run build && npm run lint
```

There are no frontend tests and no CI yet.

## Docs

- Target behaviour: [`maintenance_of_unstructured_logs_context.md`](maintenance_of_unstructured_logs_context.md)
- Working rules: [`AGENTS.md`](AGENTS.md)
- Requirements: [`docs/prd.md`](docs/prd.md) · Architecture: [`docs/architecture.md`](docs/architecture.md)
- Data: [`docs/memory.md`](docs/memory.md) · Rules: [`docs/rules.md`](docs/rules.md) · UI: [`docs/design.md`](docs/design.md)
- Tracker and decisions: [`docs/tasks.md`](docs/tasks.md)

Docker images (`Dockerfile`, `Dockerfile.slim`) and deploy configs (`render.yaml`,
`railway.toml`, `deploy/`, `frontend/vercel.json`) exist; no deployment has been
verified for atlogs.
