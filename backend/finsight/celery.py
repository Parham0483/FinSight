import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'finsight.settings.development')

app = Celery('finsight')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'sync-all-bank-connections': {
        'task': 'apps.banking.tasks.sync_all_active_connections',
        'schedule': crontab(minute=0, hour='*/6'),
    },
    'run-forecasts-all-orgs': {
        'task': 'apps.forecasting.tasks.run_forecasts_all_orgs',
        'schedule': crontab(minute=30, hour='*/6'),
    },
    'generate-daily-insights': {
        'task': 'apps.insights.tasks.generate_insights_all_orgs',
        'schedule': crontab(minute=0, hour=7),
    },
    'send-email-digests': {
        'task': 'apps.alerts.tasks.send_daily_digest',
        'schedule': crontab(minute=0, hour=8),
    },
    'refresh-fx-rates': {
        'task': 'apps.fx.tasks.refresh_fx_rates',
        'schedule': crontab(minute=0),
    },
    'refresh-fx-history': {
        'task': 'apps.fx.tasks.refresh_fx_history',
        'schedule': crontab(minute=0, hour=2),
    },
    'check-consent-expiry': {
        'task': 'apps.banking.tasks.check_consent_expiry',
        'schedule': crontab(minute=0, hour=9),
    },
}
