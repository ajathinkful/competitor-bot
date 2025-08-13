from fastapi import HTTPException

from app.services.openai.openai_service import OpenAIService


def validate_assistant_name(assistant_name: str):
    try:
        _config = OpenAIService(assistant_name).get_ai_assistant_config(assistant_name)
        return assistant_name
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid assistant name")
