FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (psycopg2 + playwright deps optional)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Playwright: install Chromium and system deps so PLAYWRIGHT targets work in Docker
RUN python -m playwright install --with-deps chromium

COPY . /app

# Collect static at build time (needs a placeholder SECRET_KEY when DEBUG=0)
ENV DJANGO_DEBUG=0
ENV DJANGO_SECRET_KEY=build-time-placeholder-override-in-runtime
RUN python manage.py collectstatic --noinput --clear 2>/dev/null || true

EXPOSE 8000

CMD ["gunicorn", "leads_app.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--timeout", "60"]

