#!/bin/bash
# Quick launcher: starts dictation in the background, immune to terminal
# close/hangup (SIGHUP) and closed shells. Logs go to dictation.log.
#
# Usage: ./start_dictation.sh [extra args passed to dictation.py]

cd "$(dirname "$0")"

if [ -f dictation.pid ] && kill -0 "$(cat dictation.pid)" 2>/dev/null; then
    echo "⚠️  Already running (PID $(cat dictation.pid)). Run ./stop_dictation.sh first."
    exit 1
fi
rm -f dictation.pid

if [ ! -f venv/bin/activate ]; then
    echo "❌ No virtualenv found at venv/. Create it first:"
    echo "   python3 -m venv venv && ./venv/bin/pip install -r requirements.txt"
    exit 1
fi

[ -x WisperAnk.app/Contents/MacOS/WisperAnk ] || ./build_app.sh

# Run through the app bundle so the Dock shows "WisperAnk".
nohup WisperAnk.app/Contents/MacOS/WisperAnk "$@" > /dev/null 2>&1 &
echo $! > dictation.pid
disown

echo "✅ Started (PID $(cat dictation.pid)). Logs: tail -f dictation.log"
