from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request, Depends
from typing import List, Optional, Dict
import json
from pydantic import parse_obj_as
import asyncio
from app.api.models import SectionGenerationRequest, GenerationWithTokenResponse, AnalysisPlanRequest, DocumentRequest
from app.services import processing_service, generation_service, token_service
from app.prompts import SectionName

router = APIRouter()

async def debug_and_log_form_data(request: Request):
    """
    This dependency runs before the endpoint logic. It intercepts the raw
    request and prints its form data to the console for debugging.
    """
    print("\n--- NEW REQUEST RECEIVED FOR DEBUGGING ---")
    try:
        form_data = await request.form()
        
        print("Received Form Fields and Files:")
        if not form_data:
            print("  - The form data is empty.")
        
        for key in form_data.keys():
            items = form_data.getlist(key)
            if isinstance(items[0], UploadFile):
                for file in items:
                    print(f"  - Key: '{key}', Filename: '{file.filename}', Content-Type: '{file.content_type}'")
            else:
                for value in items:
                    print(f"  - Key: '{key}', Value: '{value}'")
                    
    except Exception as e:
        print(f"!!! ERROR PARSING FORM DATA: {e} !!!")
        print("This might happen if the request is not 'multipart/form-data'.")
        
    print("--- END OF DEBUGGING LOG ---\n")

async def process_single_file(file: UploadFile) -> str:
    if not file or not file.filename: return ""
    content_type = file.content_type
    text = ""
    if "audio" in content_type: text = await processing_service.process_audio(file)
    elif "image" in content_type or "pdf" in content_type: text = await processing_service.process_pdf_or_image(file)
    else:
        try: text = (await file.read()).decode('utf-8')
        except: text = "[Unsupported file type]"
    return f"--- START OF FILE: {file.filename} ---\n{text}\n--- END OF FILE ---\n"

async def process_files(files: List[UploadFile]) -> str:
    tasks = [process_single_file(file) for file in files]
    results = await asyncio.gather(*tasks)
    return "\n".join(filter(None, results))

@router.post("/generate_section/{section_name}", response_model=GenerationWithTokenResponse, dependencies=[Depends(debug_and_log_form_data)])
async def generate_section_endpoint(
    section_name: SectionName,
    files: List[UploadFile] = File(...),
    
    request_data: str = Form(...), 
    language: str = Form(...),
    specialty: str = Form(...),
    user_id: str = Form(...)
):
    if section_name == SectionName.ANALYSIS_AND_PLAN:
        raise HTTPException(status_code=400, detail="Use the /generate_analysis_plan endpoint.")
        
    # Parse the JSON string into a SectionGenerationRequest object
    try:
        request_body = parse_obj_as(SectionGenerationRequest, json.loads(request_data))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON format for request_data.")

    # Check for tokens
    has_tokens = await token_service.check_user_tokens(user_id=user_id)
    if not has_tokens:
        raise HTTPException(status_code=402, detail="You have no tokens remaining.")

    # Process the new files for this section
    raw_input_text = await process_files(files)
    
    generated_text = await generation_service.generate_structured_text(
        previous_sections=request_body.previous_sections,
        raw_input=raw_input_text,
        section_name=section_name.value,
        # physician_notes are now inside request_body, but the new prompt doesn't use them.
        # We'll pass an empty string for now.
        physician_notes="", 
        language=language,
        specialty=specialty
    )
    
    remaining_token = await token_service.report_and_get_remaining_tokens(user_id=user_id, amount=5)
    
    return GenerationWithTokenResponse(
        section_name=section_name.value, 
        generated_text=generated_text,
        remaining_token=remaining_token
    )

@router.post("/generate_analysis_plan", response_model=GenerationWithTokenResponse)
async def generate_analysis_plan_endpoint(
    request_data: str = Form(...),
    files: List[UploadFile] = File(...)
):
    request_body = parse_obj_as(AnalysisPlanRequest, json.loads(request_data))
    has_tokens = await token_service.check_user_tokens(user_id=request_body.user_id)
    if not has_tokens:
        raise HTTPException(
            status_code=402,
            detail="You have no tokens remaining"
        )
    analysis_plan_text = await process_files(files)

    generated_text = await generation_service.generate_analysis_and_plan(
        previous_sections=request_body.previous_sections,
        analysis_plan_text=analysis_plan_text,
        physician_notes=request_body.physician_notes,
        language=request_body.language,
        specialty=request_body.specialty
    )

    remaining_token = -1
    if "[AI response was blocked" not in generated_text:
        remaining_token = await token_service.report_and_get_remaining_tokens(user_id=request_body.user_id, amount=5)

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
    extracted_text = await process_files(files)

    # --- TOKEN PRE-FLIGHT CHECK ---
    has_tokens = await token_service.check_user_tokens(user_id=user_id)
    if not has_tokens:
        raise HTTPException(
            status_code=402,
            detail="You have no tokens remaining"
        )
    
    generated_text = await generation_service.generate_structured_text(
        section_name=SectionName.QUICK_REPORT.value,
        raw_input=extracted_text, # Map 'extracted_text' to the 'raw_input' parameter
        previous_sections={},     # A quick report has no previous sections
        physician_notes="", 
        language=language,
        specialty=specialty
        # Note: The new generation_service doesn't need user_id, so we don't pass it.
    )
    
    remaining_token = -1
    if "[AI response was blocked" not in generated_text:
        remaining_token = await token_service.report_and_get_remaining_tokens(user_id=user_id, amount=5)
    
    return GenerationWithTokenResponse(
        section_name=SectionName.QUICK_REPORT.value,
        generated_text=generated_text,
        remaining_token=remaining_token
    )

# @router.post("/generate_document")
# async def generate_docx_endpoint(request: DocumentRequest):
#     """
#     Takes all generated section texts and creates a .docx file for download.
#     """
#     document = Document()
#     document.add_heading('Clinical Note', level=1)
    
#     # Ensure sections are in the correct order
#     section_order = [
#         SectionName.PRESENT_ILLNESS, SectionName.PAST_MEDICAL_HISTORY,
#         SectionName.PHYSICAL_EXAM, SectionName.LABS_AND_IMAGING,
#         SectionName.PROPOSED_DIAGNOSIS, SectionName.ANALYSIS_AND_PLAN
#     ]
    
#     for section_enum in section_order:
#         if section_enum in request.sections:
#             document.add_heading(section_enum.value, level=2)
#             document.add_paragraph(request.sections[section_enum])
#             document.add_paragraph() # Add a space between sections
            
#     # Save document to an in-memory stream
#     file_stream = io.BytesIO()
#     document.save(file_stream)
#     file_stream.seek(0)
    
#     return StreamingResponse(
#         file_stream, 
#         media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
#         headers={'Content-Disposition': 'attachment; filename=clinical_note.docx'}
#     )