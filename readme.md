# Clinical Note Generation AI Service

This repository contains the AI backend service for a medical application that automates the generation of structured clinical notes from audio, image, and PDF inputs. The service is designed for physician use, supports both Spanish and English, and operates on an ephemeral architecture, meaning no patient data is permanently stored.

This service exposes a set of RESTful APIs that handle file processing, interaction with Large Language Models (LLMs), and generation of structured text.

---

## Core Technologies

-   **Backend Framework:** [FastAPI](https://fastapi.tiangolo.com/)
-   **Data Validation:** [Pydantic](https://docs.pydantic.dev/)
-   **Language & Vision Model:** [Google Gemini 1.5 Pro](https://deepmind.google/technologies/gemini/)
-   **Audio Transcription:** [OpenAI Whisper](https://github.com/openai/whisper)
-   **Document Generation:** [python-docx](https://python-docx.readthedocs.io/)
-   **Programming Language:** Python 3.9+

---

