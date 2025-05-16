web: echo "Procfile web command executed at $(date)" > /tmp/logs/procfile_check.txt && ls -la /app && pwd && python manage.py check
worker: celery -A prep_center worker -l info