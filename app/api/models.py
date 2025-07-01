# app/api/models.py
from pydantic import BaseModel
from typing import List, Optional, Dict
from app.prompts import SectionName

class GenerateSectionRequest(BaseModel):
    # This model is primarily for documentation; files are handled separately.
    physician_notes: Optional[str] = ""
    language: str = "English"
    specialty: str = "Internal Medicine" # For future customization

class AnalysisPlanRequest(BaseModel):
    previous_sections: Dict[str, str] # e.g., {"Present Illness": "Patient reports...", ...}
    physician_notes: Optional[str] = ""
    language: str = "English"
    specialty: str = "Internal Medicine"

class GeneratedSectionResponse(BaseModel):
    section_name: str
    generated_text: str

class DocumentRequest(BaseModel):
    sections: Dict[SectionName, str]
    language: str = "English"