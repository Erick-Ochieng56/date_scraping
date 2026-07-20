# Production image for Northflank (and any other container host).
#
# Multi-stage: builds the React SPA, then a single Python image that can run as
# the web server, the Celery worker, or both combined (START_MODE=all) — the
# combined mode is what the Northflank free tier uses, since it only allows two
# services total (this app + Redis). See NORTHFLANK_DEPLOY.md.

# ---------- Stage 1: React SPA build ----------
FROM node:22-alpine AS frontend

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


# ---------- Stage 2: Django + Celery ----------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# bash: needed by deploy/start.sh (wait -n). curl: container health checks.
# build-essential/libpq-dev are only needed while pip installs; purged in the
# same layer to keep the final image small.
COPY backend/requirements.txt /app/requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends bash curl build-essential libpq-dev \
    && pip install --no-cache-dir -r /app/requirements.txt \
    && apt-get purge -y build-essential libpq-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Playwright + Chromium adds ~700MB and Chromium regularly OOMs inside the
# free tier's small containers, so it's off by default. Playwright-type scrape
# targets fail cleanly without it ("Playwright is not available"); plain-HTML
# targets and the crawler are unaffected. Enable with a build arg once on a
# paid plan with bigger containers: --build-arg INSTALL_PLAYWRIGHT=1
ARG INSTALL_PLAYWRIGHT=0
RUN if [ "$INSTALL_PLAYWRIGHT" = "1" ]; then \
      python -m playwright install --with-deps chromium; \
    fi

COPY backend/ /app/
COPY --from=frontend /frontend/dist /frontend/dist
COPY deploy/start.sh /start.sh
RUN chmod +x /start.sh

# Django serves the SPA (staff UI at /, admin portal at /admin) from this dir
# when DJANGO_SERVE_SPA=1 — no separate frontend service needed.
ENV DJANGO_REACT_DIST_DIR=/frontend/dist

# Collect Django admin/DRF static for WhiteNoise. The placeholder secret only
# exists for this build step; the real DJANGO_SECRET_KEY comes from runtime env.
RUN DJANGO_DEBUG=0 DJANGO_SECRET_KEY=build-time-placeholder \
    python manage.py collectstatic --noinput

# Run as non-root (Celery warns loudly about root workers, and there's no reason
# to be root). /app must stay writable: celery beat persists its schedule file
# there, and the sqlite fallback DB lands there when DATABASE_URL is unset.
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["/start.sh"]
