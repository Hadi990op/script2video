#!/usr/bin/env bash
# Setup for GitHub Codespaces / devcontainer
set -e

echo "=== Installing ffmpeg ==="
sudo apt-get update
sudo apt-get install -y --no-install-recommends ffmpeg

echo "=== Installing Python deps ==="
pip install --upgrade pip
pip install flask edge-tts yt-dlp

echo "=== Preparing secrets ==="
mkdir -p secrets
if [ ! -f secrets/groq.key ]; then
    # Codespaces users can set the GROQ_API_KEY repository secret instead
    if [ -n "$GROQ_API_KEY" ]; then
        echo "$GROQ_API_KEY" > secrets/groq.key
        echo "secrets/groq.key created from GROQ_API_KEY env var."
    else
        echo "WARNING: No Groq API key found."
        echo "Add it to secrets/groq.key or set the GROQ_API_KEY Codespace secret."
        echo "Get a free key at: https://console.groq.com/keys"
    fi
fi

echo "=== Setup complete! ==="
echo "Start the app with:  python3 server.py"
