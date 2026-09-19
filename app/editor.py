"""Video assembly: cut 6-8s clips, add word-by-word captions, render 16:9 and 9:16.
"""
import random
import subprocess
import tempfile
from pathlib import Path

import random


def probe_duration(path: Path) -> float:
    """Get media duration in seconds."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return float(res.stdout.strip())


def cut_clip(src: Path, out: Path, duration: float = 7.0) -> Path:
    """Cut a random 6-8s clip from the middle of the source video."""
    dur = probe_duration(src)
    if dur <= duration:
        # Video shorter than needed — use whole thing
        start = 0
        duration = dur
    else:
        start = random.uniform(0.2, max(0.2, dur - duration - 0.2))
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-ss", f"{start:.2f}",
        "-i", str(src),
        "-t", f"{duration:.2f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-an",
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
        str(out),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


def build_ass_captions(words, width: int, height: int, ass_path: Path):
    """Build a word-by-word ASS subtitle file (one word at a time).

    words: list of {"word","start","end"}
    """
    font_size = int(height * 0.075)
    # Position text ~15% up from the bottom (lower-middle area)
    margin_v = int(height * 0.15)
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,Arial,{font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,1,2,40,40,{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for w in words:
        start = _ts(w["start"])
        end = _ts(w["end"])
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{w['word']}")

    ass_path.write_text("\n".join(lines))
    return ass_path


def _ts(seconds: float) -> str:
    """Format seconds as ASS timestamp H:MM:SS.cc"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def render(voiceover: Path, words, clips, out_path: Path, size: str = "1280x720"):
    """Assemble final video: clips + voiceover + word captions.

    size: '1280x720' or '1080x1920'
    """
    w, h = map(int, size.split("x"))
    tmp = out_path.parent / "tmp_render"
    tmp.mkdir(parents=True, exist_ok=True)

    # 1. Normalize clips to target size
    norm = []
    for i, c in enumerate(clips):
        out = tmp / f"norm_{i:03d}.mp4"
        vf = (
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1"
        )
        cmd = [
            "ffmpeg", "-y", "-v", "error", "-i", str(c),
            "-vf", vf, "-an",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            str(out),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        norm.append(out)

    # 2. Concat clips
    concat_list = tmp / "concat.txt"
    concat_list.write_text(
        "\n".join(f"file '{p}'" for p in norm)
    )
    concatenated = tmp / "concat.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list), "-c", "copy",
        str(concatenated),
    ], check=True, capture_output=True)

    # 3. Burn captions + add voiceover
    ass_path = tmp / "captions.ass"
    build_ass_captions(words, w, h, ass_path)

    # Total video length = voiceover length
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-i", str(concatenated),
        "-i", str(voiceover),
        "-vf", f"ass={ass_path}",
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(out_path),
    ], check=True, capture_output=True)
    return out_path
