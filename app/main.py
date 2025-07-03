# app/main.py
from fastapi import FastAPI
from app.api.endpoints import router as api_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Clinical Note Generation AI Service",
    description="API for generating structured clinical notes from audio, images, and PDFs.",
    version="1.0.0"
)

origins = [
    "http://localhost",       
    "http://localhost:3000",  
    "http://localhost:8080",  
    "http://localhost:4200",  

]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"status": "AI Service is running"}