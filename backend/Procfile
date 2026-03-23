web: gunicorn leads_app.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 4 --timeout 60
worker: celery -A leads_app worker -l info
beat: celery -A leads_app beat -l info
