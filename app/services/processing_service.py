from openai import AsyncOpenAI
from fastapi import UploadFile
import base64
import io
from PIL import Image
import pillow_heif
import magic
import fitz
import hashlib
from functools import lru_cache
from typing import Optional

from app.core.config import settings

# Initialize client
try:
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
except Exception as e:
    print(f"--- FATAL: FAILED TO INITIALIZE OPENAI CLIENT ---")
    print(f"Error: {e}")
    client = None

# Simple in-memory cache for processed files (use Redis in production)
_file_cache = {}
MAX_CACHE_SIZE = 100

def get_file_hash(file_bytes: bytes) -> str:
    """Generate a hash for file content to use as cache key"""
    return hashlib.md5(file_bytes).hexdigest()

def cache_result(file_hash: str, result: str):
    """Store result in cache with size limit"""
    if len(_file_cache) >= MAX_CACHE_SIZE:
        # Remove oldest entry (simple FIFO)
        _file_cache.pop(next(iter(_file_cache)))
    _file_cache[file_hash] = result

def get_cached_result(file_hash: str) -> Optional[str]:
    """Retrieve cached result if available"""
    return _file_cache.get(file_hash)


# --- OPTIMIZED: Fast, Local PDF Processing ---
def process_pdf_locally(file_bytes: bytes) -> str:
    """Extract text from PDF using PyMuPDF with caching"""
    try:
        # Check cache first
        file_hash = get_file_hash(file_bytes)
        cached = get_cached_result(file_hash)
        if cached:
            print("✓ PDF result retrieved from cache")
            return cached
        
        text = ""
        # Use context manager efficiently
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            # Extract text from all pages at once (faster)
            text = "\n".join(page.get_text() for page in doc)
        
        result = text.strip()
        cache_result(file_hash, result)
        print("✓ Successfully extracted text from PDF locally")
        return result
    except Exception as e:
        print(f"✗ Error processing PDF: {e}")
        return "[Error extracting text from PDF document.]"


# --- OPTIMIZED: Audio Processing with Caching ---
async def process_audio_with_api(file: UploadFile, file_bytes: bytes) -> str:
    """Transcribe audio with caching to avoid redundant API calls
    
    Args:
        file: The UploadFile object (for filename metadata)
        file_bytes: The actual file content as bytes (already read)
    """
    if not client:
        return "[Error: OpenAI Client not initialized.]"
    
    try:
        # Check cache first
        file_hash = get_file_hash(file_bytes)
        cached = get_cached_result(file_hash)
        if cached:
            print(f"✓ Audio transcription retrieved from cache for '{file.filename}'")
            return cached
        
        # Validate file size (Whisper API limit is 25MB)
        MAX_SIZE = 25 * 1024 * 1024  # 25MB in bytes
        if len(file_bytes) > MAX_SIZE:
            error_msg = f"[Error: Audio file '{file.filename}' is too large ({len(file_bytes)/(1024*1024):.1f}MB). Maximum size is 25MB.]"
            print(f"✗ {error_msg}")
            return error_msg
        
        if len(file_bytes) == 0:
            error_msg = f"[Error: Audio file '{file.filename}' is empty.]"
            print(f"✗ {error_msg}")
            return error_msg
        
        # Get filename and ensure it has a proper extension
        filename = file.filename
        filename_lower = filename.lower()
        
        # Whisper API supported formats
        SUPPORTED_FORMATS = ['.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm', '.flac', '.ogg', '.opus']
        
        # Check if file has a supported extension
        has_valid_ext = any(filename_lower.endswith(ext) for ext in SUPPORTED_FORMATS)
        
        if not has_valid_ext:
            # Try to add appropriate extension based on content
            # Default to .m4a for unknown audio types
            filename = f"{filename}.m4a"
            print(f"⚠ Added extension to filename: {filename}")
        
        # Create file-like object from bytes
        audio_file = io.BytesIO(file_bytes)
        audio_file.name = filename
        
        print(f"→ Transcribing audio: {filename} ({len(file_bytes)/(1024):.1f}KB)")
        
        # Transcribe with Whisper API
        transcription = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text"  # Faster than JSON
        )
        
        result = transcription if isinstance(transcription, str) else transcription.text
        result = result.strip()
        
        if not result:
            result = "[No speech detected in audio file.]"
            print(f"⚠ No speech detected in '{file.filename}'")
        else:
            print(f"✓ Successfully transcribed '{file.filename}' ({len(result)} characters)")
        
        cache_result(file_hash, result)
        return result
        
    except Exception as e:
        error_msg = str(e)
        print(f"✗ Error transcribing '{file.filename}': {error_msg}")
        
        # Provide specific error messages
        if "Invalid file format" in error_msg or "format" in error_msg.lower():
            return f"[Error: Unsupported audio format for '{file.filename}'. Supported: MP3, M4A, WAV, FLAC, OGG, OPUS, WEBM]"
        elif "size" in error_msg.lower():
            return f"[Error: Audio file '{file.filename}' exceeds 25MB limit.]"
        elif "timeout" in error_msg.lower():
            return f"[Error: Transcription timeout for '{file.filename}'. File may be too long.]"
        else:
            return f"[Error transcribing '{file.filename}': {error_msg}]"


# --- OPTIMIZED: Smart Image Processing ---
async def process_image_with_api(file: UploadFile, file_bytes: bytes) -> str:
    """Analyze images with smart preprocessing and caching
    
    Args:
        file: The UploadFile object (for filename metadata)
        file_bytes: The actual file content as bytes (already read)
    """
    if not client:
        return "[Error: OpenAI Client not initialized.]"
    
    try:
        filename = file.filename.lower()
        
        # Check cache before expensive processing
        file_hash = get_file_hash(file_bytes)
        cached = get_cached_result(file_hash)
        if cached:
            print(f"✓ Image analysis retrieved from cache for '{file.filename}'")
            return cached
        
        if len(file_bytes) == 0:
            error_msg = f"[Error: Image file '{file.filename}' is empty.]"
            print(f"✗ {error_msg}")
            return error_msg
        
        # Determine mime type
        try:
            mime_type = magic.from_buffer(file_bytes, mime=True)
        except:
            mime_type = "image/jpeg"  # Default fallback
        
        print(f"→ Analyzing image: {file.filename} ({len(file_bytes)/(1024):.1f}KB)")
        
        # Optimize image
        processed_bytes = await _optimize_image(file_bytes, filename, mime_type)
        
        # Encode to base64
        base64_image = base64.b64encode(processed_bytes).decode('utf-8')
        
        # Shortened prompt for faster processing
        prompt = "Provide a concise clinical description of this medical image focusing on observable characteristics."
        
        response = await client.chat.completions.create(
            model="gpt-4o-mini",  # Faster and cheaper than gpt-4o
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                                "detail": "low"  # Faster processing
                            }
                        }
                    ]
                }
            ],
            max_tokens=512  # Reduced for faster response
        )
        
        result = response.choices[0].message.content
        cache_result(file_hash, result)
        print(f"✓ Successfully analyzed image '{file.filename}'")
        return result
        
    except Exception as e:
        print(f"✗ Error analyzing image '{file.filename}': {e}")
        return f"[Error processing image: {file.filename}]"


async def _optimize_image(file_bytes: bytes, filename: str, mime_type: str) -> bytes:
    """Optimize image size and format for API processing"""
    try:
        # Handle HEIC conversion
        if filename.endswith(('.heic', '.heif')) or "heic" in mime_type or "heif" in mime_type:
            pillow_heif.register_heif_opener()
            image = Image.open(io.BytesIO(file_bytes))
        elif "image" in mime_type and "svg" not in mime_type:
            image = Image.open(io.BytesIO(file_bytes))
        else:
            return file_bytes  # Return original if not standard image
        
        # Aggressive resizing for faster uploads (1024x1024 max)
        MAX_SIZE = (1024, 1024)
        image.thumbnail(MAX_SIZE, Image.Resampling.LANCZOS)
        
        # Convert to RGB if necessary (RGBA, P modes)
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')
        
        # Compress to JPEG with good quality/size balance
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=75, optimize=True)
        optimized_bytes = buffer.getvalue()
        
        # Only use optimized version if it's actually smaller
        if len(optimized_bytes) < len(file_bytes):
            print(f"  Image optimized: {len(file_bytes)} -> {len(optimized_bytes)} bytes")
            return optimized_bytes
        
        return file_bytes
        
    except Exception as e:
        print(f"⚠ Image optimization failed: {e}. Using original.")
        return file_bytes