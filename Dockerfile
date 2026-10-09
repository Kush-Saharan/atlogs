# Atlas backend — portable image (Hugging Face Spaces, Render, Fly, any Docker
# host). Single worker on purpose: the in-memory ingest-job registry and the
# asyncpg pool assume one process. Listens on $PORT (HF Spaces sets 7860).
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HUB_DISABLE_SYMLINKS=1 \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1 \
    HF_HOME=/app/.hf \
    PORT=7860

WORKDIR /app

# System libs Docling/torch image handling may load at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libgl1 \
 && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY backend/ ./

# Pre-download Docling models at build time so the FIRST PDF ingest is not a
# cold model download. Best-effort: if the CLI name changes, models simply
# download on first use instead (slower once).
RUN python -m docling.cli.models download 2>/dev/null \
 || docling-tools models download 2>/dev/null \
 || echo "Docling model pre-download skipped; will download on first ingest."

EXPOSE 7860

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1"]
