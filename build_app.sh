#!/bin/bash
# Builds WisperAnk.app: a copy of the venv's Python binary inside an app
# bundle, so the Dock shows "WisperAnk" instead of "Python".
# start_dictation.sh runs it automatically if the bundle is missing.
set -e
cd "$(dirname "$0")"

APP=WisperAnk.app
REAL_PY="$(./venv/bin/python -c 'import sys; print(sys._base_executable)')"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp "$REAL_PY" "$APP/Contents/MacOS/WisperAnk"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>WisperAnk</string>
  <key>CFBundleDisplayName</key><string>WisperAnk</string>
  <key>CFBundleIdentifier</key><string>local.wisperank</string>
  <key>CFBundleExecutable</key><string>WisperAnk</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>NSMicrophoneUsageDescription</key><string>WisperAnk records your voice to transcribe it.</string>
</dict></plist>
PLIST
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true
echo "Built $APP"
