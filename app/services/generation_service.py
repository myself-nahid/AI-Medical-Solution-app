# app/services/generation_service.py

from openai import AsyncOpenAI
from typing import Dict

from app.core.config import settings
from app.prompts import get_prompt_for_section

# Initialize the AsyncOpenAI client
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

async def generate_structured_text(
    section_name: str, 
    raw_input: str,
    previous_sections: Dict[str, str],
    physician_notes: str, 
    specialty: str,
    language: str = "English"
) -> str:
    """Generates a structured paragraph using an OpenAI chat model."""
    prompt_template = get_prompt_for_section(section_name)
    
    cumulative_context = ""
    if previous_sections:
        cumulative_context += "--- START OF PREVIOUSLY GENERATED SECTIONS ---\n"
        for sec_name, sec_text in previous_sections.items():
            cumulative_context += f"## {sec_name}:\n{sec_text}\n\n"
        cumulative_context += "--- END OF PREVIOUSLY GENERATED SECTIONS ---\n\n"
    
    full_context = f"{cumulative_context}--- START OF NEW INFORMATION ---\n{raw_input}"
    
    final_prompt = prompt_template.format(
        language=language,
        context=full_context,
        specialty=specialty
    )
    
    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo", # Use fast, cost-effective model for this
            messages=[{"role": "user", "content": final_prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error during OpenAI text generation for section '{section_name}': {e}")
        return "[AI text generation failed.]"


async def generate_analysis_and_plan(
    previous_sections: Dict[str, str],
    analysis_plan_text: str,
    physician_notes: str,
    specialty: str,
    language: str = "English"
) -> str:
    """Generates the Analysis and Plan section using the powerful gpt-4o model."""
    prompt_template = get_prompt_for_section("Analysis and Plan")
    
    previous_context = "\n\n".join(f"## {section}:\n{summary}" for section, summary in previous_sections.items())
    current_context = f"--- START OF NEW INFORMATION ---\n{analysis_plan_text}"

    final_prompt = prompt_template.format(
        language=language,
        previous_summaries=previous_context,
        current_section_context=current_context,
        specialty=specialty
    )
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o", # Use powerful model for the final reasoning step
            messages=[{"role": "user", "content": final_prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error during OpenAI analysis and plan generation: {e}")
        return "[AI analysis and plan generation failed.]"