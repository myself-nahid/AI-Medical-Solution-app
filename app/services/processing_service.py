import whisper
import google.generativeai as genai
from fastapi import UploadFile
import tempfile
import os

from app.core.config import settings

# Configure Gemini
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

# --- Service Functions ---

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
            # Asynchronously read the content from the uploaded file
            content = await file.read()
            # Write the content to our new temporary file on disk
            temp_file.write(content)
            # Store the full, OS-specific path to this temporary file
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
    Extracts text and descriptions from images or PDFs using Google's Gemini 1.5 Pro model.
    This function operates directly with the file's bytes in memory, making it efficient
    as it avoids writing to the disk.
    """
    try:
        # Asynchronously read the entire file content into a bytes object in memory
        file_bytes = await file.read()
        
        # Prepare the file data payload for the Gemini API, including the MIME type
        # which is crucial for the model to know how to interpret the data.
        file_data = {
            'mime_type': file.content_type,
            'data': file_bytes
        }
        
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # A carefully crafted prompt instructing the AI on how to handle different file types.
        prompt = """
        You are an expert medical data processor. Analyze the content of the provided file.

        - If the file is a document (e.g., PDF lab report, clinical note, text on an image):
          Extract all relevant text verbatim. Preserve formatting like lists and tables where possible.
          Organize the extracted information clearly.

        - If the file is a photograph (e.g., a wound, a skin lesion, a physical finding):
          Provide a detailed, objective, and clinical description. Do NOT diagnose or interpret.
          Focus on observable characteristics like size, shape, color, texture, and surrounding tissue.
          Example: 'Image displays an elliptical, 5 cm ulcer on the medial malleolus. The wound bed is 80% covered with pink granulation tissue and 20% with yellow slough. The periwound skin shows moderate erythema and scaling.'
        """
        
        # Asynchronously call the Gemini API to generate content based on the prompt and file data.
        response = await model.generate_content_async([prompt, file_data])
        return response.text.strip()

    except Exception as e:
        print(f"Error during Gemini processing for file '{file.filename}': {e}")
        return f"[An AI processing error occurred for the file: {file.filename}]"