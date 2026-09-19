#!/usr/bin/env bash
# Setup for GitHub Codespaces / devcontainer (idempotent, Alpine AND Debian compatible)
set -e

echo "=== Detecting OS ==="
if grep -qi alpine /etc/os-release; then
    PKG="alpine"
elif grep -qiE 'debian|ubuntu' /etc/os-release; then
    PKG="debian"
else
    PKG="unknown"
fi
echo "OS: $PKG"

echo "=== Installing ffmpeg ==="
if command -v ffmpeg > /dev/null 2>&1; then
    echo "ffmpeg already installed"
elif [ "$PKG" = "alpine" ]; then
    sudo apk add --no-cache ffmpeg
else
    sudo apt-get update
    sudo apt-get install -y --no-install-recommends ffmpeg
fi

echo "=== Installing Python deps ==="
if [ "$PKG" = "alpine" ]; then
    python3 -m pip install --break-system-packages flask edge-tts yt-dlp
else
    python3 -m pip install flask edge-tts yt-dlp
fi

echo "=== Preparing secrets ==="
mkdir -p secrets
if [ ! -s secrets/groq.key ]; then
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
