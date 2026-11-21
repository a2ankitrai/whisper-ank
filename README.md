# Whisper Ank

A local speech-to-text dictation application that types transcribed text directly into any focused application on macOS. No cloud services, no API keys — everything runs locally on your machine.

![Platform](https://img.shields.io/badge/platform-macOS-blue)
![Python](https://img.shields.io/badge/python-3.9+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

---

## Table of Contents

- [Features](#features)
- [How It Works](#how-it-works)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration Options](#configuration-options)
- [Whisper Models](#whisper-models)
- [Troubleshooting](#troubleshooting)
- [Testing](#testing)
- [Architecture](#architecture)
- [Limitations](#limitations)
- [Contributing](#contributing)

---

## Features

| Feature | Description |
|---------|-------------|
| 🎤 **100% Local** | Uses Faster-Whisper — no internet, no cloud, complete privacy |
| ⌨️ **Universal Typing** | Types into ANY focused app: editors, terminals, browsers, chat apps |
| 🎯 **Push-to-Talk** | Hold `Cmd+Shift` to record (configurable), release to transcribe |
| 📝 **Auto Punctuation** | Whisper adds proper grammar, punctuation, and capitalization |
| 🚀 **Fast** | Faster-Whisper is 4x faster than standard Whisper |
| 🌍 **Multilingual** | Supports 99 languages with automatic detection |
| 🔄 **Code-Mixing** | Handles mixed languages in same sentence (e.g., English+Hindi+Dutch) |
| ✨ **Grammar Correction** | LanguageTool (rule-based) or Gramformer (AI-based) |
| 🌐 **Translation** | Whisper (any→English) + Argos Translate (English→target language) |
| 🔇 **Filler Removal** | Automatically removes "um", "uh", "like", "you know" |
| 📋 **Snippets** | Voice-triggered text shortcuts (e.g., "insert signature") |
| 🔤 **Hotwords** | Custom dictionary for proper nouns and jargon |
| 🔊 **Audio Feedback** | Beeps on record start/stop |
| 💾 **Offline** | Works without internet after initial model download |

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER WORKFLOW                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   1. Start app          2. Hold Cmd+Shift        3. Speak           │
│   ─────────────────     ──────────────────       ─────────────      │
│   $ python dictation.py  🔴 Recording...          "Hello world"     │
│                                                                      │
│   4. Release hotkey     5. Processing            6. Text appears    │
│   ─────────────────     ─────────────────        ─────────────      │
│   ⏹ Stop recording       🔄 Transcribing...       Hello world.|     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Technical Flow

1. **Hotkey Detection**: `pynput` listens for `Cmd+Shift` key combination
2. **Audio Capture**: `sounddevice` records from microphone at 16kHz
3. **Transcription**: `faster-whisper` (CTranslate2) processes audio locally
4. **Text Injection**: macOS `CGEvents` types characters into the focused app

The key innovation is using **CGEvents at the HID (Human Interface Device) level** — this simulates actual keyboard input at the OS level, making it work with any application without special integration.

---

## Prerequisites

### System Requirements

- **macOS** 10.15 (Catalina) or later
- **Python** 3.9 or later
- **RAM**: 4GB minimum (8GB+ recommended for larger models)
- **Storage**: ~500MB for base model, up to 3GB for large-v3

### Required Software

#### 1. Homebrew (if not installed)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

#### 2. FFmpeg (required by Whisper)

```bash
brew install ffmpeg
```

Verify installation:
```bash
ffmpeg -version
```

#### 3. Python 3.9+

```bash
# Check your Python version
python3 --version

# Install if needed
brew install python@3.11
```

---

## Installation

### Step 1: Clone or Download

```bash
# If using git
cd ~/your/preferred/directory
git clone <repository-url> whisper-dictation
cd whisper-dictation

# Or just navigate to the directory
cd /path/to/whisper-dictation
```

### Step 2: Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `faster-whisper` — Optimized Whisper implementation
- `sounddevice` — Audio recording
- `numpy` — Audio data processing
- `pynput` — Keyboard hotkey detection
- `pyobjc-framework-Quartz` — macOS text injection

### Step 4: Grant Permissions

#### Accessibility Permission (Required)

The app needs accessibility access to type into other applications.

1. Open **System Preferences** (or **System Settings** on Ventura+)
2. Go to **Security & Privacy** → **Privacy** → **Accessibility**
3. Click the lock 🔒 to make changes
4. Click **+** and add your Terminal app:
   - `/Applications/Utilities/Terminal.app` for Terminal
   - `/Applications/iTerm.app` for iTerm2
   - `/Applications/Visual Studio Code.app` for VS Code integrated terminal

> **Note**: If you run the script from a different terminal, add that terminal app.

#### Microphone Permission

Granted automatically on first run — just click "Allow" when prompted.

### Step 5: First Run (Downloads Model)

```bash
python dictation.py
```

On first run, the app downloads the Whisper model (~150MB for `base`). This only happens once.

---

## Usage

### Basic Usage

```bash
# Activate virtual environment
source venv/bin/activate

# Run with default settings (base model, auto-detect language)
python dictation.py
```

### Controls

| Action | Key Combination | Description |
|--------|-----------------|-------------|
| **Start Recording** | Hold `Cmd + Shift` | Microphone activates, recording begins |
| **Stop & Transcribe** | Release keys | Audio is processed and text is typed |
| **Quit** | Press `Escape` | Exits the application |

### Workflow Example

1. **Open any application** (VS Code, Slack, Notes, Terminal, etc.)
2. **Click where you want to type** (ensure cursor is focused)
3. **Run the dictation app** in a terminal
4. **Hold Cmd+Shift** and speak clearly
5. **Release** — your words appear at the cursor!

### Quick Start Script

Create an alias for convenience:

```bash
# Add to ~/.zshrc or ~/.bash_profile
alias dictate="cd ~/path/to/whisper-dictation && source venv/bin/activate && python dictation.py"
```

Then just run:
```bash
dictate
```

---

## Configuration Options

### Command-Line Arguments

```bash
python dictation.py [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--model`, `-m` | `base` | Whisper model size (see [Models](#whisper-models)) |
| `--language`, `-l` | `en` | Language code (e.g., `en`, `de`, `fr`, `es`) |
| `--grammar`, `-g` | none | Grammar engine: `languagetool` or `gramformer` |
| `--translate`, `-t` | off | Translate speech to English (any language → English) |
| `--target-language`, `-T` | none | Translate output to target language (e.g., `nl` for Dutch) |
| `--multilingual`, `-M` | off | Enable code-mixing (e.g., English+Hindi+Dutch) |
| `--keep-fillers` | off | Keep filler words (um, uh, like) in output |
| `--hotwords`, `-H` | none | Comma-separated list of proper nouns/jargon |
| `--snippets-file` | none | Path to snippets file (see below) |
| `--no-audio-feedback` | off | Disable beeps on record start/stop |
| `--hotkey` | `cmd+shift` | Custom hotkey (e.g., `ctrl+shift`). Modifiers: `cmd`, `shift`, `ctrl`, `alt` |

### Examples

```bash
# Basic dictation
python dictation.py

# With AI-powered grammar correction
python dictation.py --grammar gramformer

# Code-mixing mode (English + Hindi + Dutch in same sentence)
python dictation.py --multilingual --model medium

# Translate German speech to English
python dictation.py --language de --translate

# Speak English, output Dutch (for communication)
python dictation.py --target-language nl

# Custom dictionary for technical terms
python dictation.py --hotwords "OpenAI,Whisper,GitHub,Kubernetes"

# Custom hotkey
python dictation.py --hotkey ctrl+shift

# Maximum accuracy
python dictation.py --model large-v3 --grammar gramformer
```

### Snippets File

Create voice-triggered text shortcuts. File format (one per line):

```
# snippets.txt
signature=Best regards,\nJohn Doe
address=123 Main Street, San Francisco, CA
meeting=Let's schedule a meeting to discuss this further.
```

Usage:
```bash
python dictation.py --snippets-file snippets.txt
```

Then say "signature" or "insert signature" to expand.

### Grammar Correction Engines

| Engine | Type | Speed | Quality | Install |
|--------|------|-------|---------|---------|
| `languagetool` | Rule-based | Fast | Good | Included |
| `gramformer` | AI/Transformer | Slower | Better | `pip install -U git+https://github.com/PrithivirajDamodaran/Gramformer.git` |

### Translation

**Whisper Translation** (`--translate`): Converts speech in any language to English text. Built into Whisper, highly accurate.

**Argos Translation** (`--target-language`): Converts English output to another language. Requires:
```bash
pip install argostranslate
```
First use auto-downloads the language pack (~100MB per language pair).

### Language Codes

Common language codes:

| Language | Code | Language | Code |
|----------|------|----------|------|
| English | `en` | German | `de` |
| Spanish | `es` | French | `fr` |
| Italian | `it` | Portuguese | `pt` |
| Chinese | `zh` | Japanese | `ja` |
| Korean | `ko` | Russian | `ru` |
| Dutch | `nl` | Polish | `pl` |
| Hindi | `hi` | Arabic | `ar` |

For a complete list, see [Whisper language codes](https://github.com/openai/whisper#available-models-and-languages).

---

## Whisper Models

### Model Comparison

| Model | Parameters | Download Size | RAM Usage | Speed | Accuracy | Best For |
|-------|------------|---------------|-----------|-------|----------|----------|
| `tiny` | 39M | ~75MB | ~1GB | ⚡⚡⚡⚡ | ★★☆☆☆ | Quick tests |
| `base` | 74M | ~150MB | ~1GB | ⚡⚡⚡ | ★★★☆☆ | Daily use |
| `small` | 244M | ~500MB | ~2GB | ⚡⚡ | ★★★★☆ | Better accuracy |
| `medium` | 769M | ~1.5GB | ~5GB | ⚡ | ★★★★☆ | High accuracy |
| `large-v3` | 1550M | ~3GB | ~10GB | 🐢 | ★★★★★ | Maximum accuracy |

### Recommendations

- **Casual use / Older Macs**: `tiny` or `base`
- **Daily productivity**: `base` or `small`
- **Important documents**: `small` or `medium`
- **Professional/Legal**: `large-v3`

### Apple Silicon Note

On M1/M2/M3 Macs, Faster-Whisper uses optimized CPU inference. Performance is excellent even with the `small` model.

---

## Troubleshooting

### Common Issues

#### "Hotkey stops working / only triggers sometimes"

**Root cause**: opening and closing a CoreAudio input stream for every
dictation can deadlock inside PortAudio (`sounddevice.abort()` never returns).
That wedged the recording thread, so later hotkey presses produced no beep, no
microphone and no transcription until the app was restarted. Slow work inside
the keyboard callback made it worse: macOS silently disables an event tap whose
callback is too slow (`kCGEventTapDisabledByTimeout`).

**Fix**: Already handled by the app:
- The microphone stream is opened **once** and kept open; starting/stopping a
  recording is just a flag flip, so PortAudio teardown can never wedge it.
  (Side effect: the macOS microphone indicator stays on while the app runs.)
- Keyboard callbacks only update state and enqueue work, so they always return
  instantly; beeps are fire-and-forget and transcription runs on its own thread.
- A watchdog re-enables the event tap if macOS disables it, restarts the
  listener if it dies, and re-syncs modifier state with the hardware so a
  missed key release cannot wedge the app.

**If it still misbehaves**, the app is now debuggable instead of silent:
```bash
tail -f dictation.log                 # look for "Event tap was disabled",
                                      # "Missed key release", "stuck for Ns"
kill -USR1 $(cat dictation.pid)       # dump every thread's stack to the log
```

#### "Recording started but no text appears"

**Cause**: Accessibility permission not granted.

**Fix**:
1. Go to **System Settings** → **Privacy & Security** → **Accessibility**
2. Ensure your terminal app is in the list and enabled
3. Remove and re-add if necessary
4. Restart the terminal and try again

#### "No audio being recorded"

**Cause**: Microphone permission denied or wrong input device.

**Fix**:
1. Go to **System Settings** → **Privacy & Security** → **Microphone**
2. Ensure your terminal app has permission
3. Check your default microphone in **System Settings** → **Sound** → **Input**

#### "Model download fails"

**Cause**: Network issues or disk space.

**Fix**:
```bash
# Clear cache and retry
rm -rf ~/.cache/huggingface/hub/models--*whisper*
python dictation.py
```

#### "ffmpeg not found"

**Fix**:
```bash
brew install ffmpeg
```

#### "No module named 'Quartz'"

**Cause**: PyObjC not installed correctly.

**Fix**:
```bash
pip uninstall pyobjc-framework-Quartz pyobjc-core
pip install pyobjc-framework-Quartz
```

#### "Transcription is slow"

**Fix**: Use a smaller model:
```bash
python dictation.py --model tiny
```

Or on Apple Silicon, ensure you're using the native Python (not Rosetta):
```bash
arch -arm64 python dictation.py
```

### Debug Mode

For verbose output, modify the script or check the console output for errors.

### Getting Help

Check the application output in the terminal for error messages. Most issues are related to:
1. Missing permissions (Accessibility/Microphone)
2. Missing ffmpeg
3. Model download issues

---

## Testing

The project includes a comprehensive test suite with 75% code coverage.

### Running Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run all tests
pytest

# Run with coverage report
pytest --cov=dictation --cov-report=term-missing

# Run specific test file
pytest tests/test_audio_recorder.py

# Run with verbose output
pytest -v
```

### Test Structure

```
tests/
├── __init__.py
├── test_audio_feedback.py    # 14 tests - Audio beeps
├── test_audio_recorder.py    # 21 tests - Audio capture
├── test_config.py            # 31 tests - Configuration
├── test_dictation_app.py     # 30 tests - App orchestration
├── test_grammar_corrector.py # 11 tests - Grammar correction
├── test_integration.py       # 9 tests  - End-to-end flows
├── test_text_processors.py   # 25 tests - Filler removal, snippets
├── test_text_typer.py        # 12 tests - CGEvents typing
├── test_transcriber.py       # 20 tests - Whisper integration
└── test_translator.py        # 9 tests  - Argos translation
```

### Coverage Summary

```
Name           Stmts   Miss  Cover
----------------------------------
dictation.py     436    111    75%
----------------------------------
```

---

## Architecture

### Component Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           DictationApp                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │AudioRecorder │  │ Transcriber  │  │  Processors  │  │  TextTyper   │  │
│  │              │  │              │  │              │  │              │  │
│  │ - sounddevice│  │ - whisper    │  │ - Filler     │  │ - Quartz     │  │
│  │ - numpy      │  │ - translate  │  │ - Snippets   │  │ - CGEvents   │  │
│  │ - 16kHz mono │  │ - multilang  │  │ - Grammar    │  │ - HID level  │  │
│  │              │  │ - hotwords   │  │ - Translate  │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
│         │                 │                 │                 │          │
│         └─────────────────┴─────────────────┴─────────────────┘          │
│                                    │                                      │
│   ┌──────────────┐    ┌───────────┴───────────┐    ┌──────────────┐      │
│   │AudioFeedback │    │   pynput Listener     │    │DictationConfig│      │
│   │  - beeps     │    │   (configurable key)  │    │  - settings   │      │
│   └──────────────┘    └───────────────────────┘    └──────────────┘      │
└──────────────────────────────────────────────────────────────────────────┘
```

### Class Overview

| Class | Responsibility |
|-------|----------------|
| `DictationConfig` | Configuration dataclass with all settings |
| `AudioRecorder` | Manages microphone input via sounddevice |
| `Transcriber` | Whisper transcription with translation/multilingual support |
| `FillerRemover` | Removes "um", "uh", "like" etc. from text |
| `SnippetExpander` | Expands voice triggers to preset text |
| `LanguageToolCorrector` | Rule-based grammar correction |
| `GramformerCorrector` | AI-based grammar correction (T5 transformer) |
| `ArgosTranslator` | Offline translation (English → target language) |
| `AudioFeedback` | Plays beeps on record start/stop |
| `TextTyper` | Injects text into focused app via macOS CGEvents |
| `DictationApp` | Orchestrates workflow; builds processing pipeline |

### Processing Pipeline

```
Audio → Transcriber → FillerRemover → SnippetExpander → GrammarCorrector → Translator → TextTyper
```

### Key Technical Decisions

1. **Faster-Whisper over OpenAI Whisper**: 4x faster with CTranslate2 optimization
2. **CGEvents over AppleScript**: Works at HID level, universal app support
3. **Push-to-talk over VAD**: More reliable, no false triggers
4. **Pipeline architecture**: Modular text processors, easy to extend
5. **Lazy loading**: Grammar/translation models only load on first use
6. **Config-driven**: All settings via `DictationConfig` dataclass

---

## Limitations

### Current Limitations

- **macOS only** — Uses macOS-specific APIs (Quartz/CGEvents)
- **No GUI** — Command-line interface only
- **Gramformer install** — Requires manual pip install from GitHub
- **Translation direction** — Whisper only translates TO English; Argos needed for other directions

### Planned Features

- [ ] Menu bar app with status indicator
- [ ] Cross-platform support (Linux, Windows)
- [ ] Clipboard mode (copy instead of type)
- [ ] Voice activity detection option
- [ ] Real-time streaming transcription

---

## Contributing

### Development Setup

```bash
# Clone and setup
git clone <repository>
cd whisper-dictation
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pytest pytest-cov

# Run tests
pytest --cov=dictation
```

### Project Structure

```
whisper-dictation/
├── dictation.py        # Main application
├── requirements.txt    # Python dependencies
├── README.md          # This file
├── pytest.ini         # Test configuration
├── tests/             # Test suite
│   ├── __init__.py
│   ├── test_audio_recorder.py
│   ├── test_transcriber.py
│   ├── test_text_typer.py
│   ├── test_dictation_app.py
│   └── test_integration.py
└── venv/              # Virtual environment (not in git)
```

---

## License

MIT License — See LICENSE file for details.

---

## Acknowledgments

- [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper) — Fast Whisper implementation
- [OpenAI Whisper](https://github.com/openai/whisper) — Original speech recognition model
- [pynput](https://github.com/moses-palmer/pynput) — Keyboard monitoring
- [sounddevice](https://github.com/spatialaudio/python-sounddevice) — Audio I/O

---

<p align="center">
  Made with ❤️ by Ankit & AI
</p>
