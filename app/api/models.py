from pydantic import BaseModel
from typing import List, Optional, Dict
from app.prompts import SectionName

class GenerationRequestData(BaseModel):
    previous_sections: Optional[Dict[str, str]] = {}
    physician_notes: Optional[str] = ""

class DocumentRequest(BaseModel):
    sections: Dict[SectionName, str]
    language: str = "English"

class GenerationWithTokenResponse(BaseModel):
    section_name: str
    generated_text: str
    remaining_token: int