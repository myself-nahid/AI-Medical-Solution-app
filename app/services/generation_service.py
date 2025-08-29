# app/services/generation_service.py
import google.generativeai as genai
from typing import Dict

from app.core.config import settings
from app.prompts import get_prompt_for_section

# Configure Gemini
genai.configure(api_key=settings.GOOGLE_API_KEY)

async def generate_structured_text(
    section_name: str, 
    extracted_text: str, 
    physician_notes: str,
    language: str = "English",
    specialty: str = "Internal Medicine"
) -> str:
    """Generates a structured paragraph for a given clinical section."""
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    
    prompt_template = get_prompt_for_section(section_name)
    
    # Combine all inputs into a single context for the LLM
    full_context = f"""
    Extracted information from user-uploaded files:
    ---
    {extracted_text}
    ---
    
    Additional physician notes:
    ---
    {physician_notes if physician_notes else "No additional notes provided."}
    ---
    """
    
    final_prompt = prompt_template.format(
        language=language,
        context=full_context,
        specialty=specialty
    )
    
    response = await model.generate_content_async(final_prompt)
    return response.text.strip()

async def generate_analysis_and_plan(
    previous_sections: Dict[str, str],
    analysis_plan_text: str,
    physician_notes: str,
    language: str = "English",
    specialty: str = "Internal Medicine"
) -> str:
    """Generates the Analysis and Plan section using all previous context."""
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    
    prompt_template = get_prompt_for_section("Analysis and Plan")
    
    # Build the context from previous sections
    previous_context = "\n\n".join(
        f"## {section}:\n{summary}" for section, summary in previous_sections.items()
    )
    
    # Build the context from current uploads for this section
    current_context = f"""
    Extracted information from files uploaded for the 'Analysis and Plan' section:
    ---
    {analysis_plan_text}
    ---
    
    Additional physician notes for this section:
    ---
    {physician_notes if physician_notes else "No additional notes provided."}
    ---
    """
    
    final_prompt = prompt_template.format(
        language=language,
        previous_summaries=previous_context,
        current_section_context=current_context,
        specialty=specialty
    )
    
    response = await model.generate_content_async(final_prompt)
    return response.text.strip()