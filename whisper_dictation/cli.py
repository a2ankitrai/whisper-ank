"""Command-line entry point for the dictation application."""

from __future__ import annotations

import argparse
import os
import sys

from .config import DictationConfig
from .dictation_app import DictationApp


def main():
    parser = argparse.ArgumentParser(
        description="Local speech-to-text dictation with grammar correction and translation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python dictation.py                          # Basic dictation
  python dictation.py --grammar gramformer     # With AI grammar correction
  python dictation.py --multilingual           # Code-mixing (EN+Hindi+Dutch)
  python dictation.py --translate              # Any language → English
  python dictation.py --target-language nl     # English → Dutch translation
  python dictation.py --hotwords "OpenAI,Whisper,GitHub"
  python dictation.py --hotkey ctrl+shift      # Custom hotkey
  python dictation.py --recording-mode toggle  # Press once to start/stop
        """
    )

    # Model settings
    parser.add_argument(
        "--model", "-m",
        default="base",
        choices=["tiny", "base", "small", "medium", "large-v3"],
        help="Whisper model size (default: base)",
    )
    parser.add_argument(
        "--language", "-l",
        default="en",
        help="Language code (default: en). Use with caution when --multilingual is set.",
    )

    # Grammar correction
    parser.add_argument(
        "--grammar", "-g",
        choices=["languagetool", "gramformer"],
        default=None,
        help="Grammar correction engine (default: none)",
    )

    # Translation
    parser.add_argument(
        "--translate", "-t",
        action="store_true",
        help="Translate speech to English (Whisper's built-in translation)",
    )
    parser.add_argument(
        "--target-language", "-T",
        default=None,
        help="Translate English output to this language using Argos (e.g., 'nl' for Dutch)",
    )

    # Multilingual
    parser.add_argument(
        "--multilingual", "-M",
        action="store_true",
        help="Enable multilingual mode for code-mixing (e.g., English+Hindi+Dutch)",
    )

    # Text processing
    parser.add_argument(
        "--keep-fillers",
        action="store_true",
        help="Keep filler words (um, uh, like, etc.) in output",
    )
    parser.add_argument(
        "--hotwords", "-H",
        default=None,
        help="Comma-separated list of hotwords (proper nouns, jargon) for better recognition",
    )

    # Snippets
    parser.add_argument(
        "--snippets-file",
        default=None,
        help="Path to snippets file (format: trigger=text per line)",
    )

    # Audio feedback
    parser.add_argument(
        "--no-audio-feedback",
        action="store_true",
        help="Disable audio feedback beeps",
    )

    # Hotkey
    parser.add_argument(
        "--hotkey",
        default="cmd+shift",
        help="Hotkey combination (default: cmd+shift). Example: ctrl+shift",
    )
    parser.add_argument(
        "--recording-mode",
        choices=["push_to_talk", "toggle"],
        default="push_to_talk",
        help=(
            "push_to_talk (default): hold the hotkey to record, release to "
            "stop. toggle: press the hotkey once to start, press it again "
            "to stop."
        ),
    )
    parser.add_argument(
        "--replay-hotkey",
        default="cmd+shift+v",
        help=(
            "Hotkey that retypes the most recent transcription "
            "(default: cmd+shift+v)"
        ),
    )

    args = parser.parse_args()

    try:
        config = DictationConfig.from_args(args)
    except ValueError as e:
        parser.error(str(e))

    print("⚠️  Requires Accessibility permissions for typing into apps.")
    print("   System Preferences → Security & Privacy → Privacy → Accessibility\n")

    exit_code = 0
    try:
        app = DictationApp(config=config)
        app.run()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}", file=sys.stderr)
        exit_code = 1

    # PortAudio's atexit handler can block forever while terminating a stream,
    # which would leave a zombie process holding the hotkey. Everything of ours
    # is already cleaned up at this point, so exit hard.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)


if __name__ == "__main__":
    main()
