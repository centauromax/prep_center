web: cd backend && python manage.py runserver 0.0.0.0:$PORT
worker: cd backend && celery -A prep_center worker -l info