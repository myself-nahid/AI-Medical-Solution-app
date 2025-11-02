import google.generativeai as genai
from fastapi import UploadFile
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import io
from PIL import Image
import pillow_heif

from app.core.config import settings

# --- Configuration ---
genai.configure(api_key=settings.GOOGLE_API_KEY)


# --- Unified Processing Service ---

async def process_file_with_gemini(file: UploadFile) -> str:
    """
    Processes any supported file (audio, image, PDF) using the Gemini 1.5 API.
    This function handles transcription for audio and analysis for visual media.
    It also includes pre-processing for HEIC and other large images.
    """
    try:
        file_bytes = await file.read()
        mime_type = file.content_type
        filename = file.filename.lower()

        # --- Pre-processing for HEIC images ---
        if filename.endswith(('.heic', '.heif')):
            try:
                pillow_heif.register_heif_opener()
                image = Image.open(io.BytesIO(file_bytes))
                jpeg_buffer = io.BytesIO()
                image.save(jpeg_buffer, format="JPEG")
                file_bytes = jpeg_buffer.getvalue()
                mime_type = 'image/jpeg'
                print(f"Successfully converted HEIC file '{file.filename}' to JPEG.")
            except Exception as heic_error:
                print(f"Could not convert HEIC file '{file.filename}'. Error: {heic_error}")
                return f'The file "{file.filename}" is in HEIC format and could not be converted.'
        
        # --- Pre-processing for other large images (resizing) ---
        elif "image" in mime_type and "svg" not in mime_type:
            try:
                img = Image.open(io.BytesIO(file_bytes))
                MAX_SIZE = (2048, 2048)
                img.thumbnail(MAX_SIZE, Image.Resampling.LANCZOS)
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=85)
                processed_bytes = buffer.getvalue()
                if len(processed_bytes) < len(file_bytes):
                    print(f"Image pre-processed: Original size: {len(file_bytes)} bytes -> New size: {len(processed_bytes)} bytes")
                    file_bytes = processed_bytes
                    mime_type = "image/jpeg"
            except Exception as img_error:
                print(f"Could not resize image '{file.filename}'. Sending original. Error: {img_error}")

        # --- Prepare the file for the Gemini API ---
        file_data = {
            'mime_type': mime_type,
            'data': file_bytes
        }
        
        model = genai.GenerativeModel('gemini-2.5-flash-lite') 
        
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        # --- Use a dynamic prompt based on file type ---
        if "audio" in mime_type:
            prompt = "Transcribe the following audio. Provide a clean, verbatim transcription of the speech."
        else: # For images and PDFs
            prompt = """
            You are an expert medical data processor. Analyze the content of the provided file.
            - If it is a document (PDF, or text on an image), extract all relevant text verbatim.
            - If it is a photograph (e.g., a wound), provide a detailed, objective, clinical description.
            """
        
        response = await model.generate_content_async(
            [prompt, file_data],
            safety_settings=safety_settings
        )

        if not response.parts:
            finish_reason = response.candidates[0].finish_reason if response.candidates else 'UNKNOWN'
            return f"[AI response was blocked by content policies. Finish Reason: {finish_reason}]"
            
        return response.text.strip()

    except Exception as e:
        print(f"Error during Gemini processing for file '{file.filename}': {e}")
        return f"[An AI processing error occurred for the file: {file.filename}]"