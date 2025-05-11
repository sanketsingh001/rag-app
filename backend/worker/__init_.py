# worker/__init__.py
from .ingest import celery_app as celery   # Celery expects this attr by default
