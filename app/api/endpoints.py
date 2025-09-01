from fastapi import APIRouter, UploadFile, File, Depends, Form, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict
import io
from docx import Document

from app.api.models import GeneratedSectionResponse, AnalysisPlanRequest, DocumentRequest
from app.services import processing_service, generation_service
from app.prompts import SectionName

router = APIRouter()

import asyncio 

async def process_single_file(file: UploadFile) -> str:
    """Helper function to process one file. Moved logic here."""
    if not file or file.filename == '':
        return ""
    
    content_type = file.content_type
    text = ""
    if "audio" in content_type:
        text = await processing_service.process_audio(file)
    elif "image" in content_type or "pdf" in content_type:
        text = await processing_service.process_pdf_or_image(file)
    else:
        try:
            text_bytes = await file.read()
            text = text_bytes.decode('utf-8')
        except:
            text = "[Unsupported file type]"
            
    return f"--- START OF FILE: {file.filename} ---\n{text}\n--- END OF FILE ---\n"


async def process_files(files: List[UploadFile]) -> str:
    """Helper function to process a list of uploaded files IN PARALLEL."""
    tasks = [process_single_file(file) for file in files]
    
    results = await asyncio.gather(*tasks)
    
    return "\n".join(results)

@router.post("/generate_section/{section_name}", response_model=GeneratedSectionResponse)
async def generate_section_endpoint(
    section_name: SectionName,
    files: List[UploadFile] = File(...),
    physician_notes: Optional[str] = Form(""),
    language: str = Form(...), 
    specialty: str = Form(...),
    user_id: str = Form(...)
):
    """
    Generates a summary for any standard section (not Analysis & Plan).
    Accepts multiple files (audio, image, pdf) and optional notes.
    """
    if section_name == SectionName.ANALYSIS_AND_PLAN:
        raise HTTPException(status_code=400, detail="Use the /generate_analysis_plan endpoint for this section.")
    
    print(f"Received from frontend - Language: {language}, Specialty: {specialty}, Physician Notes: {physician_notes}, user-id: {user_id}")
    extracted_text = await process_files(files)
    
    generated_text = await generation_service.generate_structured_text(
        section_name=section_name.value,
        extracted_text=extracted_text,
        physician_notes=physician_notes,
        language=language,
        specialty="Internal Medicine"
    )
    
    return GeneratedSectionResponse(
        section_name=section_name.value, 
        generated_text=generated_text
    )

import json
from pydantic import parse_obj_as
from app.api.models import AnalysisPlanRequest

@router.post("/generate_analysis_plan", response_model=GeneratedSectionResponse)
async def generate_analysis_plan_endpoint(
    request_data: str = Form(...), 
    files: List[UploadFile] = File(...),
    user_id: str = Form(...)
):
    """
    Generates the 'Analysis and Plan' summary, considering all previous sections.
    Accepts previous section data as a JSON string and new files.
    """
    try:
        request_body = parse_obj_as(AnalysisPlanRequest, json.loads(request_data))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON format for request_data.")

    print(f"Request data: {request_data}, files: {files}, user-id: {user_id}")
    analysis_plan_text = await process_files(files)

    generated_text = await generation_service.generate_analysis_and_plan(
        previous_sections=request_body.previous_sections,
        analysis_plan_text=analysis_plan_text,
        physician_notes=request_body.physician_notes,
        language=request_body.language,
        specialty=request_body.specialty
    )
    
    response = GeneratedSectionResponse(
        section_name=SectionName.ANALYSIS_AND_PLAN.value,
        generated_text=generated_text
    )
    print("Analysis Plan Response:", response.dict())
    return response

@router.post("/quick_report", response_model=GeneratedSectionResponse)
async def quick_report_endpoint(
    files: List[UploadFile] = File(...),
    language: str = Form(...),
    specialty: str = Form(...),
    user_id: str = Form(...)
):
    """
    Generates a quick summary from uploaded files without the full clinical structure.
    """
    # process each file and print its details
    for file in files:
        print(f"Received file: {file.filename}, Content type: {file.content_type}")
        contents = await file.read()
        print(f"File size: {len(contents)} bytes")
        await file.seek(0)

    extracted_text = await process_files(files)
    
    generated_text = await generation_service.generate_structured_text(
        section_name=SectionName.QUICK_REPORT.value,
        extracted_text=extracted_text,
        physician_notes="", 
        language=language
    )
    
    response = GeneratedSectionResponse(
        section_name=SectionName.QUICK_REPORT.value,
        generated_text=generated_text
    )
    print("Quick Report Response:", response.dict())
    return response

@router.post("/generate_document")
async def generate_docx_endpoint(request: DocumentRequest):
    """
    Takes all generated section texts and creates a .docx file for download.
    """
    document = Document()
    document.add_heading('Clinical Note', level=1)
    
    # Ensure sections are in the correct order
    section_order = [
        SectionName.PRESENT_ILLNESS, SectionName.PAST_MEDICAL_HISTORY,
        SectionName.PHYSICAL_EXAM, SectionName.LABS_AND_IMAGING,
        SectionName.PROPOSED_DIAGNOSIS, SectionName.ANALYSIS_AND_PLAN
    ]
    
    for section_enum in section_order:
        if section_enum in request.sections:
            document.add_heading(section_enum.value, level=2)
            document.add_paragraph(request.sections[section_enum])
            document.add_paragraph() # Add a space between sections
            
    # Save document to an in-memory stream
    file_stream = io.BytesIO()
    document.save(file_stream)
    file_stream.seek(0)
    
    return StreamingResponse(
        file_stream, 
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        headers={'Content-Disposition': 'attachment; filename=clinical_note.docx'}
    )