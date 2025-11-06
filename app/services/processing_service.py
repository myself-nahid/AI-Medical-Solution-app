from openai import AsyncOpenAI
from fastapi import UploadFile
import base64
import io
from PIL import Image
import pillow_heif
import magic
import fitz

from app.core.config import settings

# --- Configuration ---
# Initialize the AsyncOpenAI client once and reuse it across all functions.
# This is efficient and a best practice.
try:
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
except Exception as e:
    print(f"--- FATAL: FAILED TO INITIALIZE OPENAI CLIENT ---")
    print(f"Error: {e}")
    print("Please ensure the OPENAI_API_KEY is set correctly in your .env file.")
    client = None


# --- Fast, Local PDF Processing ---
def process_pdf_locally(file_bytes: bytes) -> str:
    """
    Extracts text from a PDF's bytes using the fast PyMuPDF (fitz) library.
    This runs locally on the server and does not require an AI API call.
    """
    try:
        text = ""
        # Open the PDF from the in-memory byte stream.
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            # Iterate through each page and extract its text.
            for page in doc:
                text += page.get_text()
        print("Successfully extracted text from PDF locally.")
        return text.strip()
    except Exception as e:
        print(f"Error processing PDF locally with PyMuPDF: {e}")
        return "[Error extracting text from PDF document.]"


# --- Audio Processing with OpenAI Whisper API ---
async def process_audio_with_api(file: UploadFile) -> str:
    """Transcribes audio using the fast, GPU-powered OpenAI Whisper API."""
    if not client:
        return "[Error: OpenAI Client not initialized. Audio transcription failed.]"
    try:
        # The OpenAI library can efficiently handle the file-like object directly.
        # It streams the upload, which is good for larger files.
        transcription = await client.audio.transcriptions.create(
            model="whisper-1",
            file=(file.filename, await file.read(), file.content_type)
        )
        print(f"Successfully transcribed audio file '{file.filename}' via API.")
        return transcription.text
    except Exception as e:
        print(f"Error during OpenAI Whisper API transcription for '{file.filename}': {e}")
        return f"[Error during audio transcription API call for {file.filename}.]"


# --- Image Processing with OpenAI gpt-4o Vision Model ---
async def process_image_with_api(file: UploadFile) -> str:
    """Analyzes an image using the OpenAI gpt-4o model after pre-processing."""
    if not client:
        return "[Error: OpenAI Client not initialized. Image analysis failed.]"
    try:
        file_bytes = await file.read()
        filename = file.filename.lower()
        mime_type = magic.from_buffer(file_bytes, mime=True)

        # --- Image Pre-processing Logic ---
        # Convert HEIC files to JPEG first, as they are not widely supported by APIs.
        if filename.endswith(('.heic', '.heif')) or "heic" in mime_type or "heif" in mime_type:
            try:
                pillow_heif.register_heif_opener()
                image = Image.open(io.BytesIO(file_bytes))
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG")
                file_bytes = buffer.getvalue()
                print(f"Successfully converted HEIC file '{filename}' to JPEG.")
            except Exception as heic_error:
                print(f"Could not convert HEIC file '{filename}': {heic_error}")
                return f"[File Conversion Error: The HEIC file '{filename}' may be corrupt.]"

        # Resize other large images to speed up uploads and reduce costs.
        elif "image" in mime_type and "svg" not in mime_type:
            try:
                img = Image.open(io.BytesIO(file_bytes))
                MAX_SIZE = (2048, 2048)
                img.thumbnail(MAX_SIZE, Image.Resampling.LANCZOS)
                buffer = io.BytesIO()
                # Saving as JPEG with quality settings ensures a small file size.
                img.save(buffer, format="JPEG", quality=85)
                processed_bytes = buffer.getvalue()
                if len(processed_bytes) < len(file_bytes):
                    print(f"Image pre-processed: Original size: {len(file_bytes)} bytes -> New size: {len(processed_bytes)} bytes")
                    file_bytes = processed_bytes
            except Exception as img_error:
                print(f"Could not resize image '{filename}'. Sending original. Error: {img_error}")

        # Encode the final, processed image bytes to a base64 string for the API call.
        base64_image = base64.b64encode(file_bytes).decode('utf-8')
        
        prompt = "You are an expert medical data processor. Provide a detailed, objective, and clinical description of the provided image (e.g., a wound, a skin lesion). Do NOT diagnose or interpret. Focus on observable characteristics like size, shape, color, texture, and surrounding tissue."
        
        response = await client.chat.completions.create(
            model="gpt-4o", # gpt-4o is excellent and cost-effective for vision tasks.
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        }
                    ]
                }
            ],
            max_tokens=1024 # A generous limit for a detailed description.
        )
        print(f"Successfully analyzed image '{file.filename}' with gpt-4o.")
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"Error during OpenAI image processing for '{file.filename}': {e}")
        return f"[An AI processing error occurred for the image file: {file.filename}.]"
