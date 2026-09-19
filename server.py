"""Flask Web UI for script2video."""
import json
import uuid
import shutil
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_from_directory

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.pipeline import run_pipeline
from app import voice

BASE = Path(__file__).resolve().parent.parent
OUTPUTS = BASE / "outputs"
JOBS = BASE / "jobs"
OUTPUTS.mkdir(exist_ok=True)
JOBS.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # not used for uploads

JOBS_DB = {}  # job_id -> {status, log, result}


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
    JOBS_DB[job_id] = {"status": "running", "log": [], "result": None}

    import threading

    def run():
        job = JOBS_DB[job_id]
        job_dir = OUTPUTS / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        def on_progress(msg):
            job["log"].append(str(msg))

        try:
            outputs = run_pipeline_sync(script, voice_key, job_dir, on_progress)
            job["status"] = "done"
            job["result"] = {k: f"/outputs/{job_id}/{v.name}" for k, v in outputs.items()}
            job["result"]["editor"] = f"/editor/{job_id}"
        except Exception as e:
            job["status"] = "error"
            job["log"].append(f"Error: {e}")

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"job_id": job_id})


def run_pipeline_sync(script, voice_key, job_dir, on_progress):
    import asyncio
    return asyncio.run(_run(script, voice_key, job_dir, on_progress))


async def _run(script, voice_key, job_dir, on_progress):
    return await run_pipeline(script, voice_key, job_dir, on_progress)


@app.route("/api/status/<job_id>")
def status(job_id):
    job = JOBS_DB.get(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "status": job["status"],
        "log": job["log"][-10:],
        "result": job["result"],
    })


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
