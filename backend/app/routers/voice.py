"""Voice API router — transcribes a recorded voice search into text via
Groq's hosted Whisper (reuses the existing GROQ_API_KEY, no new secret)."""

import logging

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from groq import AsyncGroq

from app.config import get_settings
from app.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

WHISPER_MODEL = "whisper-large-v3-turbo"
MAX_AUDIO_BYTES = 5 * 1024 * 1024
ALLOWED_AUDIO_TYPES = {
    "audio/webm",
    "audio/ogg",
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/m4a",
}


@router.post("/transcribe")
@limiter.limit("20/minute")
async def transcribe_audio(request: Request, file: UploadFile = File(...)) -> dict:
    """Transcribe a recorded voice search clip to text.

    Args:
        file: Audio recording (webm/mp3/wav/m4a — whatever the browser's
            MediaRecorder produced)

    Returns:
        { text: "transcribed search query" }
    """
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=400, detail="Audio file too large")
    content_type = (file.content_type or "").split(";", 1)[0].lower()
    if content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported audio format")

    try:
        settings = get_settings()
        client = AsyncGroq(api_key=settings.groq_api_key)
        transcription = await client.audio.transcriptions.create(
            model=WHISPER_MODEL,
            file=(file.filename or "voice-query.webm", audio_bytes),
            response_format="text",
        )
        text = transcription if isinstance(transcription, str) else str(transcription)
        return {"text": text.strip()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice transcription failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Voice transcription failed")
