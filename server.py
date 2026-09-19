"""Flask Web UI for script2video."""
import json
import uuid
import threading
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_from_directory

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.pipeline import run_pipeline
from app import voice

BASE = Path(__file__).resolve().parent
OUTPUTS = BASE / "outputs"
JOBS = BASE / "jobs"
OUTPUTS.mkdir(exist_ok=True)
JOBS.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # not used for uploads

JOBS_DB = {}  # job_id -> {status, log, result}
JOBS_LOCK = threading.Lock()


def save_job(job_id, job):
    """Persist job state to disk so it survives server restarts."""
    try:
        p = JOBS / f"{job_id}.json"
        p.write_text(json.dumps({
            "status": job["status"],
            "log": job["log"],
            "result": job["result"],
        }))
    except OSError:
        pass


def load_job(job_id):
    p = JOBS / f"{job_id}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def list_jobs():
    """Return recently-saved jobs (newest first)."""
    jobs = []
    for p in sorted(JOBS.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:20]:
        try:
            jobs.append({"job_id": p.stem, **json.loads(p.read_text())})
        except (OSError, json.JSONDecodeError):
            continue
    return jobs


@app.route("/")
def index():
    return render_template("index.html", voices=voice.VOICES)


@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.get_json()
    script = (data.get("script") or "").strip()
    voice_key = data.get("voice", "male_en")
    if not script:
        return jsonify({"error": "Script is required"}), 400

    job_id = uuid.uuid4().hex[:12]
    job = {"status": "running", "log": [], "result": None}
    with JOBS_LOCK:
        JOBS_DB[job_id] = job

    def run():
        job_dir = OUTPUTS / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        def on_progress(msg):
            job["log"].append(str(msg))
            save_job(job_id, job)

        try:
            outputs = run_pipeline_sync(script, voice_key, job_dir, on_progress)
            job["status"] = "done"
            job["result"] = {k: f"/outputs/{job_id}/{v.name}" for k, v in outputs.items()}
            job["result"]["editor"] = f"/editor/{job_id}"
        except Exception as e:
            job["status"] = "error"
            job["log"].append(f"Error: {e}")
        save_job(job_id, job)

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"job_id": job_id})


def run_pipeline_sync(script, voice_key, job_dir, on_progress):
    import asyncio
    return asyncio.run(_run(script, voice_key, job_dir, on_progress))


async def _run(script, voice_key, job_dir, on_progress):
    return await run_pipeline(script, voice_key, job_dir, on_progress)


@app.route("/api/status/<job_id>")
def status(job_id):
    with JOBS_LOCK:
        job = JOBS_DB.get(job_id)
    if not job:
        job = load_job(job_id)
        if not job:
            return jsonify({"error": "not found"}), 404
    return jsonify({
        "status": job["status"],
        "log": job["log"][-10:],
        "result": job["result"],
    })


@app.route("/api/preview/<job_id>")
def preview(job_id):
    """List downloaded raw clips for live preview while the pipeline runs."""
    clips_dir = OUTPUTS / job_id / "temp" / "clips"
    if not clips_dir.exists():
        return jsonify({"clips": []})
    clips = sorted(f.name for f in clips_dir.iterdir()
                   if f.suffix.lower() in (".mp4", ".webm", ".mkv"))
    return jsonify({"clips": [f"/outputs/{job_id}/temp/clips/{c}" for c in clips]})


@app.route("/api/jobs")
def api_list_jobs():
    """Recent jobs, so users can find a running/finished job after leaving the page."""
    return jsonify({"jobs": list_jobs()})


@app.route("/outputs/<path:filename>")
def outputs(filename):
    return send_from_directory(OUTPUTS, filename)


# ---------- Editor ----------

@app.route("/editor/<job_id>")
def editor_page(job_id):
    return render_template("editor.html", job_id=job_id)


@app.route("/api/timeline/<job_id>")
def timeline(job_id):
    job_dir = OUTPUTS / job_id
    tl_file = job_dir / "timeline.json"
    if not tl_file.exists():
        return jsonify({"error": "timeline not found"}), 404
    timeline = json.loads(tl_file.read_text())
    return jsonify(timeline)



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
