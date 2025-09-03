from fastapi import APIRouter, HTTPException, UploadFile, File

from backend.ml.speech_to_text import transcribe_audio

router = APIRouter()

@router.post("/transcribe-audio")
async def transcribe_audio_endpoint(audio_file: UploadFile = File(...)):
    """
    Endpoint to transcribe an audio file into text.
    """
    audio_contents = await audio_file.read()
    transcribed_text = transcribe_audio(audio_contents)
    if transcribed_text:
        return {"transcribed_text": transcribed_text}
    else:
        raise HTTPException(status_code=500, detail="Audio transcription failed.")
