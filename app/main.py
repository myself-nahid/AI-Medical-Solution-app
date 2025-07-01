# app/main.py
from fastapi import FastAPI
from app.api.endpoints import router as api_router

app = FastAPI(
    title="Clinical Note Generation AI Service",
    description="API for generating structured clinical notes from audio, images, and PDFs.",
    version="1.0.0"
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"status": "AI Service is running"}