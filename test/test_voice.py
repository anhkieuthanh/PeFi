import math
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def generate_sine_wav(path: Path, duration_s=1.0, freq=440.0, sr=16000):
    n_samples = int(duration_s * sr)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        for i in range(n_samples):
            t = i / sr
            val = 0.3 * math.sin(2 * math.pi * freq * t)
            packed = struct.pack("<h", int(val * 32767))
            wf.writeframes(packed)


@pytest.mark.integration
def test_conversion_and_transcription(tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg not available")

    # find sample ogg if present
    sample_ogg = REPO_ROOT / "voice" / "uploads" / "audio.oga"
    if sample_ogg.exists():
        ogg_path = tmp_path / "sample.oga"
        ogg_path.write_bytes(sample_ogg.read_bytes())
    else:
        # generate a WAV and convert to OGG via ffmpeg
        wav = tmp_path / "sine.wav"
        generate_sine_wav(wav)
        ogg_path = tmp_path / "sine.oga"
        subprocess.run([ffmpeg, "-y", "-i", str(wav), str(ogg_path)], check=True)

    # Convert ogg -> wav suitable for STT
    wav_conv = tmp_path / "conv.wav"
    subprocess.run(
        [ffmpeg, "-y", "-i", str(ogg_path), "-ar", "16000", "-ac", "1", "-sample_fmt", "s16", str(wav_conv)], check=True
    )
    assert wav_conv.exists()

    # Transcribe using local model (tiny) to keep it light
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from voice.model import VietnameseModel

    model = VietnameseModel("tiny")
    text = model.transcribe(str(wav_conv), language="vi")
    assert isinstance(text, str)
