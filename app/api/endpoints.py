# app/api/endpoints.py
from fastapi import APIRouter, UploadFile, File, Depends, Form, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict
import io
from docx import Document

from app.api.models import GeneratedSectionResponse, AnalysisPlanRequest, DocumentRequest
from app.services import processing_service, generation_service
from app.prompts import SectionName

router = APIRouter()

async def process_files(files: List[UploadFile]) -> str:
    """Helper function to process a list of uploaded files."""
    extracted_texts = []
    for file in files:
        if not file or file.filename == '':
            continue
        
        content_type = file.content_type
        if "audio" in content_type:
            text = await processing_service.process_audio(file)
        elif "image" in content_type or "pdf" in content_type:
            text = await processing_service.process_pdf_or_image(file)
        else:
            # Simple text extraction for other file types as a fallback
            try:
                text = (await file.read()).decode('utf-8')
            except:
                text = "[Unsupported file type]"
        
        extracted_texts.append(f"--- START OF FILE: {file.filename} ---\n{text}\n--- END OF FILE ---\n")
    
    return "\n".join(extracted_texts)

@router.post("/generate_section/{section_name}", response_model=GeneratedSectionResponse)
async def generate_section_endpoint(
    section_name: SectionName,
    files: List[UploadFile] = File(...),
    physician_notes: Optional[str] = Form(""),
    language: str = Form("English")
):
    """
    Generates a summary for any standard section (not Analysis & Plan).
    Accepts multiple files (audio, image, pdf) and optional notes.
    """
    if section_name == SectionName.ANALYSIS_AND_PLAN:
        raise HTTPException(status_code=400, detail="Use the /generate_analysis_plan endpoint for this section.")

    extracted_text = await process_files(files)
    
    generated_text = await generation_service.generate_structured_text(
        section_name=section_name.value,
        extracted_text=extracted_text,
        physician_notes=physician_notes,
        language=language
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
    # The parameters here MUST match the keys you use in Postman's form-data
    request_data: str = Form(...), 
    files: List[UploadFile] = File(...)
):
    """
    Generates the 'Analysis and Plan' summary, considering all previous sections.
    Accepts previous section data as a JSON string and new files.
    """
    try:
        # This line parses the JSON string from the form into our Pydantic model
        request_body = parse_obj_as(AnalysisPlanRequest, json.loads(request_data))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON format for request_data.")

    analysis_plan_text = await process_files(files)

    generated_text = await generation_service.generate_analysis_and_plan(
        previous_sections=request_body.previous_sections,
        analysis_plan_text=analysis_plan_text,
        physician_notes=request_body.physician_notes,
        language=request_body.language
    )
    
    return GeneratedSectionResponse(
        section_name=SectionName.ANALYSIS_AND_PLAN.value,
        generated_text=generated_text
    )
    
@router.post("/quick_report", response_model=GeneratedSectionResponse)
async def quick_report_endpoint(
    files: List[UploadFile] = File(...),
    language: str = Form("English")
):
    """
    Generates a quick summary from uploaded files without the full clinical structure.
    """
    extracted_text = await process_files(files)
    
    generated_text = await generation_service.generate_structured_text(
        section_name=SectionName.QUICK_REPORT.value,
        extracted_text=extracted_text,
        physician_notes="", # No notes for quick reports
        language=language
    )
    
    return GeneratedSectionResponse(
        section_name=SectionName.QUICK_REPORT.value,
        generated_text=generated_text
    )

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