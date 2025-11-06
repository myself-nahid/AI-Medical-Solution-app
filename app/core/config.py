import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    TOKEN_API_URL: str = os.getenv("TOKEN_API_URL")
    CHECK_TOKEN_API_URL: str = os.getenv("CHECK_TOKEN_API_URL")

settings = Settings()