import whisper
import google.generativeai as genai
from fastapi import UploadFile
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import tempfile
import os

from app.core.config import settings

genai.configure(api_key=settings.GOOGLE_API_KEY)


try:
    whisper_model = whisper.load_model("base")
except Exception as e:
    print("--- WHISPER MODEL LOADING ERROR ---")
    print(f"Error: {e}")
    print("This might be due to a missing FFmpeg installation or network issues.")
    print("Please ensure FFmpeg is installed and accessible in your system's PATH.")
    print("Application will continue to run, but audio processing will be disabled.")
    print("-----------------------------------")
    whisper_model = None


async def process_audio(file: UploadFile) -> str:
    """
    Transcribes an audio file to text using Whisper in a robust, cross-platform manner.
    This function creates a temporary file on disk because the Whisper library requires
    a file path to operate, primarily due to its dependency on FFmpeg.
    """
    if not whisper_model:
        return "[Error: Whisper model could not be loaded. Please check the server logs for details.]"

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        result = whisper_model.transcribe(temp_path, fp16=False)
        
        return result.get("text", f"[Transcription for {file.filename} resulted in empty text.]")

    except Exception as e:
        print(f"Error during audio transcription for file '{file.filename}': {e}")
        return f"[An error occurred while processing the audio file: {file.filename}]"
    
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

async def process_pdf_or_image(file: UploadFile) -> str:
    """
    Extracts text and descriptions from images or PDFs using Google's Gemini model.
    This version includes crucial safety settings to allow for medical imagery.
    """
    try:
        file_bytes = await file.read()
        mime_type = file.content_type
        
        file_data = {
            'mime_type': mime_type,
            'data': file_bytes
        }
        
        model = genai.GenerativeModel('gemini-2.5-pro')
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        prompt = """
        You are an expert medical data processor. Analyze the content of the provided file.

        - If it is a photograph (e.g., a wound, a skin lesion, a physical finding):
          Provide a detailed, objective, and clinical description. Do NOT diagnose or interpret.
          Focus on observable characteristics like size, shape, color, texture, and surrounding tissue.
        """
        
        response = await model.generate_content_async(
            [prompt, file_data],
            safety_settings=safety_settings
        )
        
        if not response.parts:
            finish_reason = response.candidates[0].finish_reason if response.candidates else 'UNKNOWN'
            print(f"Gemini response blocked. Finish Reason: {finish_reason}")
            return f"[AI response was blocked by content policies. Finish Reason: {finish_reason}]"
            
        return response.text.strip()

    except Exception as e:
        print(f"Error during Gemini processing for file '{file.filename}': {e}")
        return f"[An AI processing error occurred for the file: {file.filename}]"