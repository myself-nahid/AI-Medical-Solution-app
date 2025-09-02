from pydantic import BaseModel
from typing import List, Optional, Dict
from app.prompts import SectionName

class GenerateSectionRequest(BaseModel):
    physician_notes: Optional[str] = ""
    language: str = "English"
    specialty: str = "Internal Medicine" 

class AnalysisPlanRequest(BaseModel):
    user_id: str  
    previous_sections: Dict[str, str]
    physician_notes: Optional[str] = ""
    language: str
    specialty: str

class GeneratedSectionResponse(BaseModel):
    section_name: str
    generated_text: str

class DocumentRequest(BaseModel):
    sections: Dict[SectionName, str]
    language: str = "English"

class GenerationWithTokenResponse(BaseModel):
    section_name: str
    generated_text: str
    remaining_token: int