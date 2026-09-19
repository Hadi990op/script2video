"""End-to-end pipeline: script -> LLM scenes -> clips -> voiceover -> videos + editor timeline."""
import json
import shutil
from pathlib import Path

from . import llm, fetcher, voice, editor

VOICES = voice.VOICES


async def run_pipeline(script: str, voice_key: str, job_dir: Path,
                       on_progress=None):
    """Run the full pipeline. Returns dict with paths to output videos."""
    def log(msg):
        if on_progress:
            on_progress(msg)

    temp = job_dir / "temp"
    clips_dir = temp / "clips"
    temp.mkdir(parents=True, exist_ok=True)
    clips_dir.mkdir(parents=True, exist_ok=True)

    # 0. Find a working proxy (VM IP is YouTube-blocked)
    log("Finding working proxies...")
    proxies = fetcher.find_working_proxies(max_proxies=5)
    if not proxies:
        raise RuntimeError(
            "No working proxy found for YouTube. Try again later.")
    log(f"Found {len(proxies)} working proxies")

    # 1. LLM scene analysis
    log("Analyzing script with AI...")
    scenes = llm.analyze_script(script)
    if not scenes:
        raise ValueError("Script is empty")
    log(f"{len(scenes)} scenes detected (AI)")
    for i, s in enumerate(scenes):
        log(f"Scene {i+1}: '{s['search_terms']}' ({s['mood']})")

    # 2. Download clips for each scene via proxy
    clips = []
    for i, scene in enumerate(scenes):
        query = scene["search_terms"] + " stock footage"
        log(f"Scene {i+1}: searching '{query}'...")
        try:
            files = fetcher.download_via_proxy(
                f"ytsearch2:{query}", clips_dir, proxies)
            clips.append({"path": files[0], "scene": scene})
        except Exception as e:
            log(f"Scene {i+1} failed: {e}")
    if not clips:
        raise RuntimeError("No clips could be downloaded")
    log(f"Downloaded {len(clips)} clips")

    # 3. Generate voiceover
    log("Generating voiceover...")
    vo_path = temp / "voiceover.mp3"
    timings_path = temp / "words.json"
    words = await voice.generate_voiceover(
        script, VOICES[voice_key], vo_path, timings_path)
    log(f"Voiceover done ({len(words)} words)")

    # 4. Cut clips to match voiceover duration
    log("Cutting clips...")
    cut_dir = temp / "cut"
    cut_dir.mkdir(exist_ok=True)
    vo_duration = editor.probe_duration(vo_path)
    n_needed = max(1, len(clips))
    log(f"Voiceover is {vo_duration:.1f}s, {n_needed} clips")
    cut_clips = []
    for i, item in enumerate(clips):
        out = cut_dir / f"clip_{i:03d}.mp4"
        try:
            cut_clips.append(editor.cut_clip(Path(item["path"]), out))
        except Exception as e:
            log(f"Cut failed: {e}")
    if not cut_clips:
        raise RuntimeError("No clips could be cut")

    # 5. Render both aspect ratios
    outputs = {}
    for label, size in [("16x9", "1280x720"), ("9x16", "1080x1920")]:
        log(f"Rendering {label}...")
        out_path = job_dir / f"final_{label}.mp4"
        editor.render(vo_path, words, cut_clips, out_path, size)
        outputs[label] = out_path

    # 6. Build editor timeline JSON (references kept temp files)
    timeline = _build_timeline(job_dir, temp, words, cut_clips, clips, vo_duration)
    (job_dir / "timeline.json").write_text(json.dumps(timeline, indent=2))

    return outputs


def _build_timeline(job_dir, temp, words, cut_clips, clips, vo_duration):
    """Build timeline JSON consumed by the editor UI."""
    clip_entries = []
    for i, (item, cut) in enumerate(zip(clips, cut_clips)):
        scene = item["scene"]
        clip_entries.append({
            "id": i,
            "file": f"temp/cut/{cut.name}",
            "search_terms": scene["search_terms"],
            "mood": scene["mood"],
            "scene_text": scene["text"],
            "duration": editor.probe_duration(cut),
        })
    return {
        "duration": vo_duration,
        "voiceover": "temp/voiceover.mp3",
        "words": words,
        "clips": clip_entries,
    }
