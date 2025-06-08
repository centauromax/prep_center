release: cd backend && ./deploy.sh
web: cd backend && gunicorn prep_center.wsgi --log-file -
worker: cd backend && celery -A prep_center worker -l info