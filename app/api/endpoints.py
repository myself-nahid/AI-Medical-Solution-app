from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List, Optional, Dict
import json
from pydantic import parse_obj_as
import asyncio
import io
from docx import Document
import magic

from app.api.models import GenerationRequestData, GenerationWithTokenResponse, DocumentRequest
from app.services import processing_service, generation_service, token_service
from app.prompts import SectionName

router = APIRouter()


# --- File Processing Helpers (Unchanged) ---
async def process_single_file(file: UploadFile) -> str:
    """Helper function to process one file by routing it to the correct service."""
    if not file or not file.filename:
        return ""
    
    file_bytes = await file.read()
    await file.seek(0)
    
    mime_type = magic.from_buffer(file_bytes, mime=True)
    
    text = ""
    if "audio" in mime_type:
        text = await processing_service.process_audio_with_api(file)
    elif "pdf" in mime_type:
        text = processing_service.process_pdf_locally(file_bytes)
    elif "image" in mime_type or file.filename.lower().endswith(('.heic', '.heif')):
        text = await processing_service.process_image_with_api(file)
    else:
        text = f"[Unsupported file type: {mime_type}]"
            
    return f"--- START OF FILE: {file.filename} ---\n{text}\n--- END OF FILE ---\n"

async def process_files(files: List[UploadFile]) -> str:
    """Processes a list of uploaded files in parallel."""
    if not files:
        return ""
    tasks = [process_single_file(file) for file in files]
    results = await asyncio.gather(*tasks)
    return "\n".join(filter(None, results))


# --- API Endpoints (Updated with Parallel Logic) ---

@router.post("/generate_section/{section_name}", response_model=GenerationWithTokenResponse)
async def generate_section_endpoint(
    section_name: SectionName,
    files: List[UploadFile] = File(...),
    request_data: str = Form(...),
    language: str = Form(...),
    specialty: str = Form(...),
    user_id: str = Form(...)
):
    if section_name == SectionName.ANALYSIS_AND_PLAN:
        raise HTTPException(status_code=400, detail="Use the dedicated /generate_analysis_plan endpoint.")

    try:
        request_body = parse_obj_as(GenerationRequestData, json.loads(request_data))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON format for request_data.")
        
    has_tokens = await token_service.check_user_tokens(user_id=user_id)
    if not has_tokens:
        raise HTTPException(status_code=402, detail="You have no tokens remaining.")

    raw_input_text = await process_files(files)
    
    # --- START: PARALLEL EXECUTION ---
    # Create two tasks that can run concurrently
    generation_task = generation_service.generate_structured_text(
        previous_sections=request_body.previous_sections,
        raw_input=raw_input_text,
        section_name=section_name.value,
        physician_notes=request_body.physician_notes, 
        language=language,
        specialty=specialty
    )
    token_reporting_task = token_service.report_and_get_remaining_tokens(user_id=user_id, amount=5)

    # Run both tasks at the same time and wait for both to complete
    results = await asyncio.gather(generation_task, token_reporting_task)
    
    generated_text = results[0]
    remaining_token = results[1]
    # --- END: PARALLEL EXECUTION ---
    
    return GenerationWithTokenResponse(
        section_name=section_name.value, 
        generated_text=generated_text,
        remaining_token=remaining_token
    )

@router.post("/generate_analysis_plan", response_model=GenerationWithTokenResponse)
async def generate_analysis_plan_endpoint(
    files: List[UploadFile] = File(...),
    request_data: str = Form(...),
    language: str = Form(...),
    specialty: str = Form(...),
    user_id: str = Form(...)
):
    try:
        request_body = parse_obj_as(GenerationRequestData, json.loads(request_data))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON format for request_data.")
        
    has_tokens = await token_service.check_user_tokens(user_id=user_id)
    if not has_tokens:
        raise HTTPException(status_code=402, detail="You have no tokens remaining.")
        
    analysis_plan_text = await process_files(files)

    # --- START: PARALLEL EXECUTION ---
    generation_task = generation_service.generate_analysis_and_plan(
        previous_sections=request_body.previous_sections,
        analysis_plan_text=analysis_plan_text,
        physician_notes=request_body.physician_notes,
        language=language,
        specialty=specialty
    )
    token_reporting_task = token_service.report_and_get_remaining_tokens(user_id=user_id, amount=5)

    results = await asyncio.gather(generation_task, token_reporting_task)
    generated_text = results[0]
    remaining_token = results[1]
    # --- END: PARALLEL EXECUTION ---

    return GenerationWithTokenResponse(
        section_name=SectionName.ANALYSIS_AND_PLAN.value,
        generated_text=generated_text,
        remaining_token=remaining_token
    )

@router.post("/quick_report", response_model=GenerationWithTokenResponse)
async def quick_report_endpoint(
    files: List[UploadFile] = File(...),
    language: str = Form(...),
    specialty: str = Form(...),
    user_id: str = Form(...)
):
    has_tokens = await token_service.check_user_tokens(user_id=user_id)
    if not has_tokens:
        raise HTTPException(
            status_code=402,
            detail="You have no tokens remaining"
        )
    
    extracted_text = await process_files(files)
    
    # --- START: PARALLEL EXECUTION ---
    generation_task = generation_service.generate_structured_text(
        section_name=SectionName.QUICK_REPORT.value,
        raw_input=extracted_text,
        previous_sections={},
        physician_notes="", 
        language=language,
        specialty=specialty
    )
    token_reporting_task = token_service.report_and_get_remaining_tokens(user_id=user_id, amount=5)

    results = await asyncio.gather(generation_task, token_reporting_task)
    generated_text = results[0]
    remaining_token = results[1]
    # --- END: PARALLEL EXECUTION ---
    
    return GenerationWithTokenResponse(
        section_name=SectionName.QUICK_REPORT.value,
        generated_text=generated_text,
        remaining_token=remaining_token
    )

# @router.post("/generate_document")
# async def generate_docx_endpoint(request: DocumentRequest):
#     """
#     Takes all generated section texts and creates a .docx file for download.
#     This does not cost tokens and is not parallelized.
#     """
#     document = Document()
#     document.add_heading('Clinical Note', level=1)
    
#     section_order = [
#         SectionName.PRESENT_ILLNESS, SectionName.PAST_MEDICAL_HISTORY,
#         SectionName.PHYSICAL_EXAM, SectionName.LABS_AND_IMAGING,
#         SectionName.PROPOSED_DIAGNOSIS, SectionName.ANALYSIS_AND_PLAN
#     ]
    
#     for section_enum in section_order:
#         if section_enum in request.sections:
#             document.add_heading(section_enum.value, level=2)
#             document.add_paragraph(request.sections[section_enum])
#             document.add_paragraph()
            
#     file_stream = io.BytesIO()
#     document.save(file_stream)
#     file_stream.seek(0)
    
#     return StreamingResponse(
#         file_stream, 
#         media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
#         headers={'Content-Disposition': 'attachment; filename=clinical_note.docx'}
#     )