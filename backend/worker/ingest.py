from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "worker",
    broker=settings.redis_url,   # redis://redis:6379/0
    backend=settings.redis_url,
    task_serializer="json",
    result_serializer="json",
)

@celery_app.task(name="ingest_document")   # <— THIS decorator is mandatory
def ingest_document(file_id: str, filename: str) -> str:
    # heavy-lifting placeholder
    print("Ingesting", filename)
    return "ok"