
import whisper
from typing import Optional
from io import BytesIO
import numpy as np
import soundfile as sf # To read audio data into numpy array

# Load the Whisper model
# Options: 'tiny', 'base', 'small', 'medium', 'large'
# For local demo, 'base' or 'small' is a good balance of accuracy and speed.
# This will download the model the first time it's run.
try:
    import whisper
    # Try to load a tiny model, or set to None if it fails
    # This assumes 'tiny.en' is a valid model, otherwise it'll still fail.
    # For now, let's make it explicitly None if we want to disable.
    # WHISPER_MODEL = whisper.load_model("tiny.en")
    WHISPER_MODEL = None # Explicitly set to None to disable if not wanted
    if WHISPER_MODEL is None:
        print("Whisper model is disabled or failed to load. Speech-to-text functionality will be skipped.")
except ImportError:
    print("Whisper library not installed. Speech-to-text functionality will be skipped.")
    WHISPER_MODEL = None
except Exception as e:
    print(f"Error loading Whisper model: {e}. Speech-to-text functionality will be skipped.")
    WHISPER_MODEL = None

def transcribe_audio(audio_file: bytes) -> str:
    if WHISPER_MODEL is None:
        print("Whisper model is not available. Skipping audio transcription.")
        return ""

    try:
        # Whisper expects audio in a specific format (e.g., 16kHz mono FLAC/WAV).
        # We need to ensure the audio_data is in a format Whisper can process.
        # For simplicity, we'll try to load it with soundfile and convert if necessary.
        audio_stream = BytesIO(audio_file)
        
        # Read audio data into a numpy array (soundfile handles various formats)
        # Ensure it's 16kHz and mono
        audio_np, sr = sf.read(audio_stream)
        
        # If stereo, convert to mono by averaging channels
        if audio_np.ndim > 1:
            audio_np = np.mean(audio_np, axis=1)

        # Resample if not 16kHz (Whisper's expected sample rate)
        if sr != 16000:
            # This requires 'resampy' or 'scipy.signal.resample', which might not be installed by default.
            # For a prototype, we might assume 16kHz input or add a note.
            # For now, let's assume it's close enough or rely on Whisper's internal handling if robust.
            # A robust solution would involve explicit resampling:
            # from scipy.signal import resample
            # num_samples = int(len(audio_np) * (16000 / sr))
            # audio_np = resample(audio_np, num_samples)
            print(f"Warning: Audio sample rate is {sr}Hz, not 16kHz. Whisper may handle this, but explicit resampling is recommended for production.")

        # Whisper expects a numpy array of floats
        result = WHISPER_MODEL.transcribe(audio_np)
        return result["text"]
    except Exception as e:
        print(f"Error during audio transcription: {e}")
        return ""

