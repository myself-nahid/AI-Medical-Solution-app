# app/main.py
from fastapi import FastAPI

app = FastAPI(
    title="Clinical Note Generation AI Service",
    description="API for generating structured clinical notes from audio, images, and PDFs.",
    version="1.0.0"
)

@app.get("/")
def read_root():
    return {"status": "AI Service is running"}