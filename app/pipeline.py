"""End-to-end pipeline: script -> keywords -> clips -> voiceover -> final videos."""
import shutil
from pathlib import Path

from . import extract, fetcher, voice, editor

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

    # 1. Extract keywords per scene
    log("Extracting keywords from script...")
    scenes = extract.extract_keywords(script)
    if not scenes:
        raise ValueError("Script is empty")
    log(f"{len(scenes)} scenes detected")

    # 2. Download clips for each scene via proxy
    clips = []
    for i, scene in enumerate(scenes):
        if not scene["keywords"]:
            continue
        query = " ".join(scene["keywords"]) + " stock footage"
        log(f"Scene {i+1}: searching '{query}'...")
        try:
            files = fetcher.download_via_proxy(
                f"ytsearch2:{query}", clips_dir, proxies)
            clips.extend(files)
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

    # 4. Cut clips: 6s each, enough to cover full voiceover
    log("Cutting clips...")
    cut_dir = temp / "cut"
    cut_dir.mkdir(exist_ok=True)
    vo_duration = editor.probe_duration(vo_path)
    clip_len = 6.0
    n_needed = int(vo_duration / clip_len) + (1 if vo_duration % clip_len else 0)
    n_needed = max(1, n_needed)
    log(f"Voiceover is {vo_duration:.1f}s, need {n_needed} clips of {clip_len:.0f}s")
    cut_clips = []
    i = 0
    while len(cut_clips) < n_needed:
        c = clips[i % len(clips)]  # cycle through sources if needed
        out = cut_dir / f"clip_{i:03d}.mp4"
        try:
            cut_clips.append(editor.cut_clip(Path(c), out, duration=clip_len))
        except Exception as e:
            log(f"Cut failed for {c}: {e}")
        i += 1
        if i >= n_needed * 3 and not cut_clips:
            break
    if not cut_clips:
        raise RuntimeError("No clips could be cut")

    # 5. Render both aspect ratios
    outputs = {}
    for label, size in [("16x9", "1280x720"), ("9x16", "1080x1920")]:
        log(f"Rendering {label}...")
        out_path = job_dir / f"final_{label}.mp4"
        editor.render(vo_path, words, cut_clips, out_path, size)
        outputs[label] = out_path

    shutil.rmtree(temp, ignore_errors=True)
    return outputs
