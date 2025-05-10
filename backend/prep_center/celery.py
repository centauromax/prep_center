import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prep_center.settings')

app = Celery('prep_center')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Configure Celery to use Redis as broker
app.conf.broker_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
app.conf.result_backend = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Configure task settings
app.conf.task_serializer = 'json'
app.conf.result_serializer = 'json'
app.conf.accept_content = ['json']
app.conf.timezone = 'Europe/Rome'
app.conf.enable_utc = True

# Set task time limits
app.conf.task_time_limit = 3600  # 1 hour
app.conf.task_soft_time_limit = 3000  # 50 minutes

# Configure task routing
app.conf.task_routes = {
    'prep_management.tasks.*': {'queue': 'prep_management'},
} 