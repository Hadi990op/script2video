# script2video

Turn any narration script into a short documentary-style video with real footage, AI voiceover, and word-by-word captions.

## How it works

1. **Script → AI scene analysis** — a Groq LLM breaks your script into visual scenes and generates search terms for **real footage** of the subject (archival clips, match footage, interviews — not generic stock).
2. **YouTube search & download** — clips are found and downloaded via `yt-dlp`, routed through working public proxies (the server IP is bot-blocked by YouTube).
3. **AI voiceover** — Microsoft Edge TTS (via `edge-tts`) generates narration with word-level timings.
4. **Automatic editing** — clips are cut to 6–8s each, matched to the voiceover duration, captioned word-by-word (karaoke style).
5. **Render** — output in both **16:9** (YouTube) and **9:16** (TikTok/Reels/Shorts).
6. **Editor timeline** — every job produces a `timeline.json` + web editor UI for reviewing clips.

## Features

- 🎙️ 4 voices: English & Urdu, male & female
- 🎬 Dual aspect-ratio rendering (16:9 + 9:16)
- 📝 Word-by-word karaoke captions
- 🖼️ Built-in web editor for reviewing/reordering clips
- 🚫 Stock-footage filter — searches for real subject footage

## Setup

```bash
# System dependencies
apt install -y ffmpeg python3-pip

# Python dependencies
pip install flask edge-tts

# Secrets
mkdir -p secrets
echo "your-groq-api-key" > secrets/groq.key

# Run
python3 server.py
```

The server listens on `http://0.0.0.0:8000`.

## Usage

**Web UI:** Open `http://localhost:8000` — paste your script, pick a voice, hit generate.

**API:**

```bash
# Start a job
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"script": "Pelé. The name itself echoes...", "voice": "male_en"}'
# -> {"job_id": "abc123"}

# Poll status
curl http://localhost:8000/api/status/abc123
# -> {"status": "done", "result": {"16x9": "...", "9x16": "...", "editor": "..."}}

# Editor
curl http://localhost:8000/editor/abc123
```

## Project structure

```
server.py          # Flask app: web UI + API
app/
  pipeline.py      # End-to-end orchestration
  llm.py           # Groq script -> scene analysis
  fetcher.py       # yt-dlp proxy-routed downloads
  voice.py         # edge-tts voiceover generation
  editor.py        # ffmpeg cutting, captions, rendering
  extract.py       # Rule-based keyword fallback
templates/         # Web UI + editor UI
```

## Notes

- YouTube downloads route through public HTTP proxies because datacenter IPs are bot-blocked. If no proxies are reachable, jobs fail with a clear error.
- One Groq API key is needed (free tier works) — place it in `secrets/groq.key`.
