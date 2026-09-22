#!/bin/bash
# Stops the background dictation process started by start_dictation.sh.

cd "$(dirname "$0")"

if [ ! -f dictation.pid ]; then
    echo "⚠️  No dictation.pid found, nothing to stop."
    exit 1
fi

PID=$(cat dictation.pid)
if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    # Escalate if the process is wedged in a blocking system call.
    for _ in 1 2 3 4 5; do
        kill -0 "$PID" 2>/dev/null || break
        sleep 1
    done
    if kill -0 "$PID" 2>/dev/null; then
        echo "⚠️  PID $PID did not exit, sending SIGKILL."
        kill -9 "$PID" 2>/dev/null
    fi
    echo "✅ Stopped (PID $PID)."
else
    echo "⚠️  Process $PID not running."
fi

rm -f dictation.pid
