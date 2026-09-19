"""Groq LLM integration: script -> semantic scene descriptions.

Uses Groq's free API (gpt-oss-20b) to analyze the script and produce
per-scene visual descriptions + search terms for REAL YouTube footage
(actual archival/broadcast clips), not generic stock footage.
Falls back to rule-based extraction if the API fails.
"""
import json
import re
import urllib.request
import urllib.error
from pathlib import Path

from . import extract

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-20b"
KEY_PATH = Path(__file__).parent.parent / "secrets" / "groq.key"

SYSTEM_PROMPT = """You are a professional documentary editor. The user gives you a narration script for a short video. Break it into visual scenes and decide what REAL FOOTAGE should be shown for each scene.

CRITICAL RULES:
- We will download real YouTube videos. These must be ACTUAL footage of the subject (e.g. real match footage, real interviews, real archival recordings), NOT generic stock clips.
- Identify the MAIN SUBJECT of the script (a person, team, event, place). EVERY search_terms MUST contain the subject's name.
- Think like a documentary researcher: what would you type into YouTube to find real footage? E.g. for Pelé's childhood -> "Pelé early career Santos", for his World Cup goals -> "Pelé 1970 World Cup goals".
- If the subject lived before color video, remember their footage is archival / black and white.
- If a scene has no filmable real footage of the subject, search for real news or documentary clips about the subject instead of generic stock.
- Each scene should cover 3-7 seconds of narration.

Return ONLY a JSON array, no markdown, no explanation:
[{"search_terms": "...", "mood": "calm", "text": "the scene narration text"}]

mood is one of: calm, energetic, tense, sad, happy, neutral."""


def _api_key() -> str:
    return KEY_PATH.read_text().strip()


def analyze_script(script: str, max_scenes: int = 12) -> list:
    """Analyze script via Groq. Returns list of scenes.
    Falls back to rule-based extract.extract_keywords() on any failure.
    """
    try:
        scenes = _call_groq(script, max_scenes)
        if scenes:
            return scenes
    except Exception:
        pass  # fall through to fallback

    # Fallback: rule-based
    return _fallback(script, max_scenes)


def _call_groq(script: str, max_scenes: int) -> list:
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": script},
        ],
        "max_tokens": 2000,
        "temperature": 0.3,
    }).encode()

    req = urllib.request.Request(
        GROQ_API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
            "User-Agent": "script2video/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)

    raw = data["choices"][0]["message"]["content"].strip()
    scenes = _parse_json_array(raw)
    return scenes[:max_scenes]


def _parse_json_array(raw: str) -> list:
    """Parse LLM output, tolerating markdown fences and stray text."""
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    result = []
    for item in arr:
        if not isinstance(item, dict):
            continue
        search = (item.get("search_terms") or "").strip()
        text = (item.get("text") or "").strip()
        if not search or not text:
            continue
        result.append({
            "text": text,
            "search_terms": search,
            "mood": item.get("mood", "neutral"),
        })
    return result


def _fallback(script: str, max_scenes: int) -> list:
    """Fallback to rule-based keyword extraction."""
    scenes = extract.extract_keywords(script, max_scenes)
    return [
        {
            "text": scene["text"],
            "search_terms": " ".join(scene["keywords"]),
            "mood": "neutral",
        }
        for scene in scenes
        if scene.get("keywords")
    ]
