from fastapi import FastAPI
from app.api import upload

app = FastAPI()

app.include_router(upload.router,prefix ="/upload")

@app.get("/hello")
async def hello():
    return {"msg": "Backend is alive!"}
