"""Voiceover generation with edge-tts (Microsoft Edge TTS, free, realistic).

Generates audio + word-level timing data for karaoke captions.
"""
import asyncio
import json
from pathlib import Path

import edge_tts

VOICES = {
    "male_en": "en-US-ChristopherNeural",
    "female_en": "en-US-JennyNeural",
    "male_ur": "ur-PK-AsadNeural",
    "female_ur": "ur-PK-UzmaNeural",
}


async def generate_voiceover(text: str, voice: str, out_mp3: Path, timings_path: Path):
    """Generate voiceover audio and word-level timings (JSON)."""
    communicate = edge_tts.Communicate(text, voice, boundary="WordBoundary")
    words = []
    with open(out_mp3, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({
                    "word": chunk["text"],
                    "start": chunk["offset"] / 1e7,  # 100ns ticks -> seconds
                    "end": (chunk["offset"] + chunk["duration"]) / 1e7,
                })
    timings_path.write_text(json.dumps(words, indent=2))
    return words
