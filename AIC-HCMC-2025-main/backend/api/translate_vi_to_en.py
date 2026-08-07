from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()
class TextInput(BaseModel):
    text: str


@router.post("/translate/")
async def translate_text(input: TextInput, request: Request):
    try:
        # Get translator from state
        
        # Translate text from Vietnamese to English
        english_text = request.app.state.vi_to_en_translator.translate(input.text)
        
        return {
            "english_text": english_text
        }
        
    except Exception as e:
        return {
            "error": f"Failed to translate text: {str(e)}",
            "english_text": ""
        }
