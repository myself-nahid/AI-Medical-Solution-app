import google.generativeai as genai
from fastapi import UploadFile
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import io
from PIL import Image
import pillow_heif
import magic  # Library for detecting file types from content
import fitz   # PyMuPDF library for fast PDF processing

from app.core.config import settings

# --- Configuration ---
genai.configure(api_key=settings.GOOGLE_API_KEY)


# --- START: New, Fast PDF Processing Function ---
def process_pdf_locally(file_bytes: bytes) -> str:
    """
    Extracts text from a PDF's bytes using the fast PyMuPDF (fitz) library.
    This runs locally and is much faster than sending a PDF to an AI for OCR.
    """
    try:
        text = ""
        # Open the PDF from the in-memory byte stream
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            # Iterate through each page and extract its text
            for page in doc:
                text += page.get_text()
        print("Successfully extracted text from PDF locally.")
        return text.strip()
    except Exception as e:
        print(f"Error processing PDF locally with PyMuPDF: {e}")
        return "[Error extracting text from PDF document.]"
# --- END: New, Fast PDF Processing Function ---


async def process_file_with_gemini(file: UploadFile) -> str:
    """
    Processes uploaded files by routing PDFs to a fast local extractor and
    sending audio/image files to the Gemini 2.5 API for analysis.
    """
    try:
        file_bytes = await file.read()
        
        # --- START: SERVER-SIDE FILE TYPE VALIDATION ---
        # Use python-magic to detect the actual MIME type from the file's content.
        # This is more reliable than trusting the Content-Type header from the client.
        detected_mime_type = magic.from_buffer(file_bytes, mime=True)
        print(f"File '{file.filename}' received. Client-sent Content-Type: '{file.content_type}', Server-detected MIME Type: '{detected_mime_type}'")
        
        # --- START: Smart Routing Logic ---
        # If the file is a PDF, use the new fast local processor and return early.
        if 'pdf' in detected_mime_type:
            return process_pdf_locally(file_bytes)
        # --- END: Smart Routing Logic ---

        # If it's not a PDF, continue with pre-processing and Gemini API call.
        mime_type = detected_mime_type
        filename = file.filename.lower()

        # Pre-processing for HEIC images
        if filename.endswith(('.heic', '.heif')) or "heic" in mime_type or "heif" in mime_type:
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
                return f'[File Conversion Error: The file "{file.filename}" is in HEIC format and could not be converted.]'
        
        # Pre-processing for other large images (resizing)
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
        file_data = { 'mime_type': mime_type, 'data': file_bytes }
        
        model = genai.GenerativeModel('gemini-2.5-flash-lite') 
        
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        # Dynamic prompt based on file type (now only for non-PDFs)
        if "audio" in mime_type:
            prompt = "Transcribe the following audio. Provide a clean, verbatim transcription of the speech. Remove filler words like 'um' and 'uh'."
        elif "image" in mime_type:
            prompt = "You are an expert medical data processor. Provide a detailed, objective, and clinical description of the provided image (e.g., a wound, a skin lesion). Do NOT diagnose or interpret."
        else:
            return f"[Unsupported File Type Error: The file format '{mime_type}' is not supported for processing.]"
        
        # Call the Gemini API
        response = await model.generate_content_async([prompt, file_data], safety_settings=safety_settings)

        if not response.parts:
            finish_reason = response.candidates[0].finish_reason if response.candidates else 'UNKNOWN'
            return f"[AI_PROCESSING_ERROR]: AI response was blocked by content policies. Finish Reason: {finish_reason}"
            
        return response.text.strip()

    except Exception as e:
        print(f"Error during file processing for file '{file.filename}': {e}")
        return f"[AI_PROCESSING_ERROR]: An unexpected error occurred while processing the file: {file.filename}"