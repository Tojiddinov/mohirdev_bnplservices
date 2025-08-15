import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')


# Celery Beat Schedule
app.conf.beat_schedule = {
    'check-overdue-payments': {
        'task': 'bnpl_service.tasks.check_overdue_payments',
        'schedule': 300.0,  # Run every 5 minutes
    },
    'clean-expired-idempotency-keys': {
        'task': 'bnpl_service.tasks.clean_expired_idempotency_keys',
        'schedule': 3600.0,  # Run every hour
    },
}
