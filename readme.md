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

## Project Architecture

The service is structured to separate concerns, making it modular and maintainable.

clinical-notes-ai-service/
├── app/
│ ├── api/
│ │ ├── endpoints.py # All FastAPI endpoints (the "controller" layer)
│ │ └── models.py # Pydantic models for request/response validation
│ ├── services/
│ │ ├── generation_service.py # Core logic for interacting with the LLM
│ │ └── processing_service.py # Logic for handling audio, images, PDFs
│ ├── core/
│ │ └── config.py # Configuration management (e.g., API keys)
│ ├── main.py # FastAPI app entry point and middleware setup
│ └── prompts.py # Centralized location for all LLM prompts
├── tests/
│ ├── test_api.py # Integration tests for API endpoints
│ └── test_services.py # Unit tests for core services
├── .env # For storing secret keys (not committed)
├── .env.example # Example environment file
├── .gitignore
└── requirements.txt


---

## Prerequisites

Before you begin, ensure you have the following installed on your system:

1.  **Python (version 3.9 or higher)**
2.  **pip** (Python package installer)
3.  **FFmpeg:** This is a critical dependency for the `Whisper` audio transcription library.
    -   **Windows:** Follow the installation guide [here](https://www.gyan.dev/ffmpeg/builds/) and ensure the `bin` directory is added to your system's `PATH`.
    -   **macOS:** `brew install ffmpeg`
    -   **Linux (Debian/Ubuntu):** `sudo apt update && sudo apt install ffmpeg`

---

## Setup and Installation

Follow these steps to get the development environment running.

**1. Clone the repository:**
```bash
git clone https://github.com/myself-nahid/AI-Medical-Solution-app.git
cd AI-Medical-Solution-app