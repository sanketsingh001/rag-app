from fastapi import APIRouter, UploadFile, BackgroundTasks, HTTPException
from uuid import uuid4
from redis import Redis
from app.core.config import get_settings
from worker.ingest import ingest_document   # Celery task

router = APIRouter()
settings = get_settings()
redis = Redis.from_url(settings.redis_url, decode_responses=True)


@router.post("/")        # <-- will map to /upload/  (note the trailing slash)
async def upload_doc(file: UploadFile, background_tasks: BackgroundTasks):
    if not file.filename:
        raise HTTPException(400, "empty filename")

    file_id = str(uuid4())
    content = await file.read()           # read bytes
    redis.setex(f"file:{file_id}", 3600, content)   # tmp cache for PoC

    task = ingest_document.delay(file_id, file.filename)  # enqueue Celery task
    return {"file_id": file_id, "task_id": task.id}
