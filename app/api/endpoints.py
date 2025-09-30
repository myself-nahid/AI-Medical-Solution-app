from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from typing import List, Optional, Dict
import json
from pydantic import parse_obj_as
import asyncio
from app.api.models import GenerationWithTokenResponse, AnalysisPlanRequest, DocumentRequest
from app.services import processing_service, generation_service, token_service
from app.prompts import SectionName

router = APIRouter()

async def debug_and_log_form_data(request: Request):
    """
    This is a dependency function that will run before the endpoint.
    It will print the raw form data to the console for debugging.
    """
    print("\n--- NEW REQUEST RECEIVED ---")
    try:
        form_data = await request.form()
        print("Received form fields:")
        for key in form_data.keys():
            item = form_data.getlist(key)
            if isinstance(item[0], UploadFile):
                for file in item:
                    print(f"  - Key: '{key}', Filename: '{file.filename}', Content-Type: '{file.content_type}'")
            else:
                print(f"  - Key: '{key}', Value: '{item[0]}'")
    except Exception as e:
        print(f"!!! Could not parse form data: {e} !!!")
    print("--- END OF REQUEST DATA ---\n")

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

@router.post("/generate_section/{section_name}", response_model=GenerationWithTokenResponse)
async def generate_section_endpoint(
    section_name: SectionName,
    files: List[UploadFile] = File(...),
    physician_notes: Optional[str] = Form(""),
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
    
    generated_text = await generation_service.generate_structured_text(
        section_name=section_name.value,
        extracted_text=extracted_text,
        physician_notes=physician_notes,
        language=language,
        specialty=specialty
    )
    
    remaining_token = -1
    if "[AI response was blocked" not in generated_text:
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
    has_tokens = await token_service.check_user_tokens(user_id=user_id)
    if not has_tokens:
        raise HTTPException(
            status_code=402,
            detail="You have no tokens remaining"
        )
   
    extracted_text = await process_files(files)
    
    generated_text = await generation_service.generate_structured_text(
        section_name=SectionName.QUICK_REPORT.value,
        extracted_text=extracted_text,
        physician_notes="", 
        language=language,
        specialty=specialty
    )
    
    remaining_token = -1
    if "[AI response was blocked" not in generated_text:
        remaining_token = await token_service.report_and_get_remaining_tokens(user_id=user_id, amount=5)
    
    response = GenerationWithTokenResponse(
        section_name=SectionName.QUICK_REPORT.value,
        generated_text=generated_text,
        remaining_token=remaining_token
    )
    print(f"Quick report response: {response}")
    return response

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