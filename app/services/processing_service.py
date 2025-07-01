# app/services/processing_service.py
import whisper
import pypdf
from PIL import Image
import google.generativeai as genai
from typing import List, Union
from fastapi import UploadFile

from app.core.config import settings

# Configure Gemini
genai.configure(api_key=settings.GOOGLE_API_KEY)

# Load Whisper model (can be 'tiny', 'base', 'small', 'medium', 'large')
whisper_model = whisper.load_model("base")

async def process_audio(file: UploadFile) -> str:
    """Transcribes audio file to text using Whisper."""
    temp_path = f"/tmp/{file.filename}"
    with open(temp_path, "wb") as buffer:
        buffer.write(await file.read())
    
    result = whisper_model.transcribe(temp_path, fp16=False) # fp16=False for CPU
    return result.get("text", "")

async def process_pdf_or_image(file: UploadFile) -> str:
    """Extracts text from images or PDFs using gemini-2.5-flash multimodal capabilities."""
    file_bytes = await file.read()
    
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # Gemini can directly handle various MIME types
    # Ensure the frontend sends the correct content_type or derive it
    file_data = {
        'mime_type': file.content_type,
        'data': file_bytes
    }
    
    # A simple prompt to extract all relevant text
    prompt = "Extract all text from this document. If it is a medical document like a lab result, format it clearly. If it's an image of a wound, describe it objectively."
    
    response = await model.generate_content_async([prompt, file_data])
    return response.text