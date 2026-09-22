"""Translation using Argos Translate (offline, open-source)."""

from __future__ import annotations

import re
import sys
from abc import abstractmethod

from .text_processors import TextProcessor


class Translator(TextProcessor):
    """Abstract base class for translators."""

    @abstractmethod
    def translate(self, text: str) -> str:
        """Translate text to target language."""
        pass

    def process(self, text: str) -> str:
        """TextProcessor interface - delegates to translate()."""
        return self.translate(text)


class ArgosTranslator(Translator):
    """Translates text using Argos Translate (offline, open-source)."""

    def __init__(self, source_lang: str = "en", target_lang: str = "nl"):
        self.source_lang = source_lang
        self.target_lang = target_lang
        self._translator = None

    def _load_translator(self):
        """Lazy-load Argos Translate on first use."""
        if self._translator is None:
            try:
                import argostranslate.package
                import argostranslate.translate

                print(f"⏳ Loading Argos Translate ({self.source_lang}→{self.target_lang})...")

                # Check if the required language package is installed
                installed_languages = argostranslate.translate.get_installed_languages()
                source = next((l for l in installed_languages if l.code == self.source_lang), None)
                target = next((l for l in installed_languages if l.code == self.target_lang), None)

                if source is None or target is None:
                    print(f"⚠️  Language pack not installed. Installing...")
                    self._install_language_pack()
                    installed_languages = argostranslate.translate.get_installed_languages()
                    source = next((l for l in installed_languages if l.code == self.source_lang), None)
                    target = next((l for l in installed_languages if l.code == self.target_lang), None)

                if source and target:
                    self._translator = source.get_translation(target)
                    if self._translator:
                        print("✅ Argos Translate loaded!")
                    else:
                        print(f"⚠️  No translation available for {self.source_lang}→{self.target_lang}")
                        self._translator = "unavailable"
                else:
                    print(f"⚠️  Language pack not found for {self.source_lang}→{self.target_lang}")
                    self._translator = "unavailable"

            except ImportError as e:
                print(f"⚠️  Argos Translate not available: {e}", file=sys.stderr)
                print("   Install with: pip install argostranslate")
                self._translator = "unavailable"

        return self._translator

    def _install_language_pack(self):
        """Download and install the required language pack."""
        try:
            import argostranslate.package

            argostranslate.package.update_package_index()
            available_packages = argostranslate.package.get_available_packages()

            # Find the package for our language pair
            package = next(
                (p for p in available_packages
                 if p.from_code == self.source_lang and p.to_code == self.target_lang),
                None
            )

            if package:
                print(f"   Downloading {self.source_lang}→{self.target_lang} package...")
                argostranslate.package.install_from_path(package.download())
                print("   ✅ Language pack installed!")
            else:
                print(f"   ⚠️  No package available for {self.source_lang}→{self.target_lang}")
        except Exception as e:
            print(f"   ⚠️  Failed to install language pack: {e}")

    def translate(self, text: str) -> str:
        """Translate text to target language."""
        if not text:
            return text

        translator = self._load_translator()
        if translator == "unavailable" or translator is None:
            return text

        try:
            # Clean up punctuation issues that can confuse Argos
            # (e.g., orphaned commas from filler removal: "Hello? , how are you")
            cleaned = re.sub(r'\?\s*,\s*', '? ', text)
            cleaned = re.sub(r'\.\s*,\s*', '. ', cleaned)
            cleaned = re.sub(r'!\s*,\s*', '! ', cleaned)
            cleaned = re.sub(r',\s*,', ',', cleaned)  # double commas
            cleaned = cleaned.strip()

            # Split into sentences to translate separately
            # Argos can truncate long multi-sentence text
            sentences = re.split(r'(?<=[.!?])\s+', cleaned)

            translated_parts = []
            for sentence in sentences:
                sentence = sentence.strip()
                if sentence:
                    translated = translator.translate(sentence)
                    if translated:
                        translated_parts.append(translated)

            return ' '.join(translated_parts) if translated_parts else text
        except Exception as e:
            print(f"⚠️  Translation error: {e}", file=sys.stderr)
            return text
