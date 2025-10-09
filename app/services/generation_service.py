import google.generativeai as genai
from typing import Dict
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from app.core.config import settings
from app.prompts import get_prompt_for_section

genai.configure(api_key=settings.GOOGLE_API_KEY)

SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

async def generate_structured_text(
    section_name: str, 
    raw_input: str,  
    previous_sections: Dict[str, str], 
    physician_notes: str, 
    specialty: str,
    language: str = "English"
) -> str:
    """Generates a structured paragraph using cumulative context."""
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
    
    prompt_template = get_prompt_for_section(section_name)
    
    cumulative_context = ""
    if previous_sections:
        cumulative_context += "--- START OF PREVIOUSLY GENERATED SECTIONS ---\n"
        for sec_name, sec_text in previous_sections.items():
            cumulative_context += f"## {sec_name}:\n{sec_text}\n\n"
        cumulative_context += "--- END OF PREVIOUSLY GENERATED SECTIONS ---\n\n"
    
    full_context = f"""
    {cumulative_context}
    --- START OF NEW INFORMATION FOR CURRENT SECTION ---
    {raw_input}
    --- END OF NEW INFORMATION FOR CURRENT SECTION ---
    """
    
    final_prompt = prompt_template.format(
        language=language,
        context=full_context,
        specialty=specialty
    )
    
    response = await model.generate_content_async(
        final_prompt,
        safety_settings=SAFETY_SETTINGS
    )
    
    if response.parts:
        return response.text.strip()
    return "[AI response was blocked by content policies.]"

async def generate_analysis_and_plan(
    previous_sections: Dict[str, str],
    analysis_plan_text: str,
    physician_notes: str,
    specialty: str,
    language: str = "English"
) -> str:
    """Generates the Analysis and Plan section using all previous context."""
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
    
    prompt_template = get_prompt_for_section("Analysis and Plan")
    
    previous_context = "\n\n".join(f"## {section}:\n{summary}" for section, summary in previous_sections.items())
    current_context = f"..." 
    final_prompt = prompt_template.format(language=language, previous_summaries=previous_context, current_section_context=current_context, specialty=specialty)

    response = await model.generate_content_async(
        final_prompt,
        safety_settings=SAFETY_SETTINGS
    )

    if response.parts:
        return response.text.strip()
    else:
        return "[AI response was blocked by content policies.]"