# app/core/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY")
    # You might have other settings, like specialty JSON paths, etc.

settings = Settings()