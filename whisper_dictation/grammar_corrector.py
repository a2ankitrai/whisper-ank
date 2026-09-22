"""Grammar correction: LanguageTool (rule-based) or Gramformer (AI-based)."""

from __future__ import annotations

import sys
from abc import abstractmethod

from .text_processors import TextProcessor


class GrammarCorrector(TextProcessor):
    """Abstract base class for grammar correctors."""

    @abstractmethod
    def correct(self, text: str) -> str:
        """Apply grammar corrections to text."""
        pass

    def process(self, text: str) -> str:
        """TextProcessor interface - delegates to correct()."""
        return self.correct(text)


class LanguageToolCorrector(GrammarCorrector):
    """Corrects grammar using LanguageTool (rule-based, lazy-loaded)."""

    def __init__(self, language: str = "en-US"):
        self.language = language
        self._tool = None

    def _load_tool(self):
        """Lazy-load LanguageTool on first use."""
        if self._tool is None:
            import language_tool_python
            print("⏳ Loading LanguageTool grammar checker...")
            self._tool = language_tool_python.LanguageTool(self.language)
            print("✅ Grammar checker loaded!")
        return self._tool

    def correct(self, text: str) -> str:
        """Apply grammar corrections to text."""
        if not text:
            return text
        tool = self._load_tool()
        corrected = tool.correct(text)
        return corrected


class GramformerCorrector(GrammarCorrector):
    """Corrects grammar using Gramformer (AI-based transformer model, lazy-loaded)."""

    def __init__(self):
        self._model = None

    def _load_model(self):
        """Lazy-load Gramformer on first use."""
        if self._model is None:
            try:
                # Patch for transformers>=4.40 compatibility (use_auth_token -> token)
                import transformers
                original_from_pretrained = transformers.T5ForConditionalGeneration.from_pretrained
                def patched_from_pretrained(*args, **kwargs):
                    kwargs.pop('use_auth_token', None)
                    return original_from_pretrained(*args, **kwargs)
                transformers.T5ForConditionalGeneration.from_pretrained = patched_from_pretrained

                from gramformer import Gramformer
                import torch

                print("⏳ Loading Gramformer AI grammar checker...")
                torch.manual_seed(1212)
                # models=1 is the corrector model
                self._model = Gramformer(models=1, use_gpu=False)
                print("✅ Gramformer loaded!")
            except ImportError as e:
                print(f"⚠️  Gramformer not available: {e}", file=sys.stderr)
                print("   Install with: pip install -U git+https://github.com/PrithivirajDamodaran/Gramformer.git")
                # Fall back to pass-through
                self._model = "unavailable"
        return self._model

    def correct(self, text: str) -> str:
        """Apply AI-based grammar corrections to text."""
        if not text:
            return text

        model = self._load_model()
        if model == "unavailable":
            return text

        # Gramformer works best with individual sentences
        try:
            corrections = model.correct(text, max_candidates=1)
            if corrections:
                return list(corrections)[0]
        except Exception as e:
            print(f"⚠️  Gramformer error: {e}", file=sys.stderr)

        return text


def create_grammar_corrector(engine: str | None, language: str = "en") -> GrammarCorrector | None:
    """Factory function to create the appropriate grammar corrector."""
    if engine is None:
        return None

    engine = engine.lower()
    if engine == "languagetool":
        # Map short language codes to LanguageTool format
        lt_lang = f"{language}-US" if language == "en" else language
        return LanguageToolCorrector(language=lt_lang)
    elif engine == "gramformer":
        return GramformerCorrector()
    else:
        print(f"⚠️  Unknown grammar engine: {engine}", file=sys.stderr)
        return None
