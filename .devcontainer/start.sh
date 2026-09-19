#!/usr/bin/env bash
# Start the server on codespace boot; keeps running after this script exits.
set -e
cd /workspaces/script2video

# Kill any stale instance
pkill -f "python3.*server\.py" 2>/dev/null || true
sleep 1

# Start fresh, detached from this session
setsid nohup python3 server.py > server.log 2>&1 < /dev/null &
sleep 5
if pgrep -f "python3.*server\.py" > /dev/null; then
    echo "Server started. Log tail:"
    tail -5 server.log
else
    echo "ERROR: Server failed to start:" >&2
    tail -20 server.log >&2
    exit 1
fi
