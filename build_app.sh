#!/bin/bash
# Builds WisperAnk.app: a copy of the venv's Python inside an app bundle, so
# the Dock shows "WisperAnk" and Finder/Launchpad get an icon.
#
# Usage: ./build_app.sh            # build ./WisperAnk.app
#        ./build_app.sh --install  # also copy it to /Applications
#
# The bundle runs this repo's code from where it is now; rebuild if you move
# the repo or Homebrew upgrades Python.
set -e
cd "$(dirname "$0")"
REPO="$PWD"

APP=WisperAnk.app
PY_DIR="$(dirname "$(./venv/bin/python -c 'import sys; print(sys._base_executable)')")"
REAL_PY="$PY_DIR/../Resources/Python.app/Contents/MacOS/Python"
SITE_PACKAGES="$(./venv/bin/python -c 'import site; print(site.getsitepackages()[0])')"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$REAL_PY" "$APP/Contents/MacOS/python-real"

# Launcher: the bundle's main executable. exec keeps the process inside the
# bundle, so macOS names it after the bundle.
cat > "$APP/Contents/MacOS/WisperAnk" <<LAUNCH
#!/bin/bash
cd "$REPO"
export PYTHONPATH="$SITE_PACKAGES:$REPO"
exec "\$(dirname "\$0")/python-real" -u dictation.py "\$@" >> dictation.log 2>&1
LAUNCH
chmod +x "$APP/Contents/MacOS/WisperAnk"

# Icon: render the same emoji the Dock uses into an .icns.
ICONSET="$(mktemp -d)/WisperAnk.iconset"
mkdir "$ICONSET"
./venv/bin/python -c "
from whisper_dictation.app_identity import render_icon_png
render_icon_png('$ICONSET/big.png')"
for s in 16 32 128 256 512; do
    sips -z $s $s "$ICONSET/big.png" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
    sips -z $((s*2)) $((s*2)) "$ICONSET/big.png" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
rm "$ICONSET/big.png"
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/WisperAnk.icns"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>WisperAnk</string>
  <key>CFBundleDisplayName</key><string>WisperAnk</string>
  <key>CFBundleIdentifier</key><string>local.wisperank</string>
  <key>CFBundleExecutable</key><string>WisperAnk</string>
  <key>CFBundleIconFile</key><string>WisperAnk</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>NSMicrophoneUsageDescription</key><string>WisperAnk records your voice to transcribe it.</string>
</dict></plist>
PLIST
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true
echo "Built $APP"

if [ "$1" = "--install" ]; then
    rm -rf "/Applications/$APP"
    cp -R "$APP" /Applications/
    echo "Installed /Applications/$APP"
fi
