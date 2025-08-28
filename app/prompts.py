from enum import Enum

class SectionName(str, Enum):
    PRESENT_ILLNESS = "Present Illness"
    PAST_MEDICAL_HISTORY = "Past Medical History"
    PHYSICAL_EXAM = "Physical Examination and Calculations"
    LABS_AND_IMAGING = "Summary of Labs and Images"
    PROPOSED_DIAGNOSIS = "Proposed Diagnosis"
    ANALYSIS_AND_PLAN = "Analysis and Plan"
    QUICK_REPORT = "Quick Report"

PROMPTS = {
    SectionName.PRESENT_ILLNESS: """
    You are an expert medical scribe specializing in **{specialty}**. Based on the following context, write a concise and structured 'History of Present Illness' (HPI) paragraph in {language}.
    The paragraph should be in a narrative format, using clinical language and terminology appropriate for a **{specialty}** specialist.
    Focus only on information relevant to the HPI.
    The paragraph should be a clean, narrative format. **Do not use complex Markdown, only a single paragraph of text.**
    **Under each heading, write the findings as clean, well-formed paragraphs. Do NOT use bullet points or lists.**

    Context:
    {context}
    
    Generated HPI:
    """,
    SectionName.PAST_MEDICAL_HISTORY: """
    You are an expert medical scribe specializing in **{specialty}**. From the context below, create a list of 'Past Medical History and Risk Factors' in {language}.
    Format it as a bulleted or numbered list. Prioritize information most relevant to a **{specialty}** specialist.
    **Format the output as a Markdown bulleted list** (using `-` or `*`). Prioritize information most relevant to a **{specialty}** specialist.
    **Under each heading, write the findings as clean, well-formed paragraphs. Do NOT use bullet points or lists.**

    Context:
    {context}
    
    Generated Past Medical History:
    """,
    SectionName.PHYSICAL_EXAM: """
    You are an expert medical scribe specializing in **{specialty}**. Synthesize the provided information into a 'Physical Exam' summary in {language}.
    If numerical data like vital signs, range of motion, or measurements for ABI/BMI are present, extract them and perform calculations if necessary (e.g., calculate BMI if height and weight are given).
    Describe any physical findings from images objectively, using terminology appropriate for a **{specialty}** specialist.
    **Structure the summary using Markdown. Use bold headings for different sections of the exam** (e.g., `**Vitals:**`, `**General Appearance:**`, `**Extremities:**`). Describe findings objectively.
    **Under each heading, write the findings as clean, well-formed paragraphs. Do NOT use bullet points or lists.**

    Context:
    {context}
    
    Generated Physical Exam Summary:
    """,
    SectionName.LABS_AND_IMAGING: """
    You are an expert medical scribe specializing in **{specialty}**. Summarize the key findings from the lab reports and imaging studies provided in the context below, in {language}.
    Highlight abnormal values and significant findings. Mention the name and date of the study if available. Interpret the findings from the perspective of a **{specialty}** specialist.
    **Use Markdown to format the output. Highlight abnormal lab values using bold text (e.g., `WBC: **15.2** (High)`). For imaging reports, use bold for the 'Impression' or 'Conclusion' section.**
    **Under each heading, write the findings as clean, well-formed paragraphs. Do NOT use bullet points or lists.**

    Context:
    {context}
    
    Generated Summary of Labs and Imaging:
    """,
    SectionName.PROPOSED_DIAGNOSIS: """
    You are an expert medical diagnostician specializing in **{specialty}**. Based on the context provided, generate a list of 'Proposed Diagnoses' or differential diagnoses in {language}.
    Order them from most likely to least likely if possible. Provide a brief one-sentence justification for each, based on the clinical reasoning of a **{specialty}** specialist.
    **Format the output as a numbered list in Markdown. Make the diagnosis itself bold** (e.g., `1. **Acute Knee Strain:** Justification for this diagnosis...`). Order them from most to least likely.
    **Under each heading, write the findings as clean, well-formed paragraphs. Do NOT use bullet points or lists.**

    Context:
    {context}
    
    Generated Proposed Diagnosis:
    """,
    SectionName.ANALYSIS_AND_PLAN: """
    You are an expert medical consultant specializing in **{specialty}**. Your task is to create a comprehensive 'Analysis and Plan' section in {language}, using the clinical reasoning of a **{specialty}** specialist.
    
    **Structure your response using Markdown.**
    - **Use a heading like `### Assessment`** for your clinical synthesis, writing it as a clean, well-formed paragraph.
    - **Use a heading like `### Plan`** for the actionable steps. **Under the 'Plan' heading, write the plan as one or more clean, well-formed paragraphs. Do NOT use bullet points or a numbered list.**
    
    Synthesize all provided information into a coherent assessment and an actionable plan tailored for your specialty.
    
    **Summaries from Previous Sections:**
    {previous_summaries}
    
    **Context for Current 'Analysis and Plan' Section:**
    {current_section_context}
    
    Generated Analysis and Plan:
    """,
    SectionName.QUICK_REPORT: """
    You are an AI assistant specializing in medical data extraction for a **{specialty}** specialist. Your task is to provide a quick and concise summary of the provided information in {language}.
    If it's text, summarize it. If it's an audio transcript, clean it up and summarize. If it's a lab report or imaging study, extract the key findings. Focus on what is most relevant to the given specialty.
    **Use simple Markdown formatting (like bullet points or bold text) where appropriate to improve readability.**
    **Under each heading, write the findings as clean, well-formed paragraphs. Do NOT use bullet points or lists.**

    Context:
    {context}
    
    Generated Quick Report:
    """
}

def get_prompt_for_section(section_name: str) -> str:
    """
    Safely retrieves the prompt template for a given section name.
    Raises a ValueError if the section name is not valid.
    """
    try:
        return PROMPTS[SectionName(section_name)]
    except (KeyError, ValueError):
        raise ValueError(f"Invalid section name provided: '{section_name}'")