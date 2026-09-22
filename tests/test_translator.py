"""Tests for Translator classes."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestArgosTranslator:
    """Tests for ArgosTranslator class."""

    def test_init_stores_languages(self):
        """Should store source and target languages."""
        from dictation import ArgosTranslator
        
        translator = ArgosTranslator(source_lang="en", target_lang="nl")
        
        assert translator.source_lang == "en"
        assert translator.target_lang == "nl"

    def test_lazy_loading(self):
        """Should not load translator on initialization."""
        from dictation import ArgosTranslator
        
        translator = ArgosTranslator()
        assert translator._translator is None

    def test_handles_empty_string(self):
        """Should handle empty string without loading translator."""
        from dictation import ArgosTranslator
        
        translator = ArgosTranslator()
        result = translator.translate("")
        
        assert result == ""
        assert translator._translator is None

    def test_handles_import_error(self):
        """Should handle missing argostranslate gracefully."""
        from dictation import ArgosTranslator
        
        # Mock the import to fail
        with patch.dict(sys.modules, {'argostranslate': None, 'argostranslate.package': None, 'argostranslate.translate': None}):
            translator = ArgosTranslator()
            translator._translator = None
            
            # Should not crash
            result = translator.translate("Hello world")
            
            # Should return original text when unavailable
            assert result == "Hello world"

    def test_process_delegates_to_translate(self):
        """Should delegate process() to translate()."""
        from dictation import ArgosTranslator
        
        translator = ArgosTranslator()
        translator._translator = MagicMock()
        translator._translator.translate.return_value = "Hallo wereld"
        
        result = translator.process("Hello world")
        
        assert result == "Hallo wereld"

    def test_translate_calls_translator(self):
        """Should call the underlying translator."""
        from dictation import ArgosTranslator
        
        mock_translator = MagicMock()
        mock_translator.translate.return_value = "Bonjour le monde"
        
        translator = ArgosTranslator(source_lang="en", target_lang="fr")
        translator._translator = mock_translator
        
        result = translator.translate("Hello world")
        
        assert result == "Bonjour le monde"
        mock_translator.translate.assert_called_once_with("Hello world")

    def test_handles_translation_error(self):
        """Should handle translation errors gracefully."""
        from dictation import ArgosTranslator
        
        mock_translator = MagicMock()
        mock_translator.translate.side_effect = Exception("Translation failed")
        
        translator = ArgosTranslator()
        translator._translator = mock_translator
        
        result = translator.translate("Hello world")
        
        # Should return original text on error
        assert result == "Hello world"

    def test_unavailable_translator_returns_original(self):
        """Should return original text when translator is unavailable."""
        from dictation import ArgosTranslator
        
        translator = ArgosTranslator()
        translator._translator = "unavailable"
        
        result = translator.translate("Hello world")
        
        assert result == "Hello world"


class TestArgosTranslatorIntegration:
    """Integration tests for ArgosTranslator (require argostranslate installed)."""

    @pytest.mark.skip(reason="Requires argostranslate to be installed")
    def test_real_translation_en_to_nl(self):
        """Test actual translation from English to Dutch."""
        from dictation import ArgosTranslator
        
        translator = ArgosTranslator(source_lang="en", target_lang="nl")
        result = translator.translate("Hello world")
        
        # Should return something in Dutch
        assert result != "Hello world"
        assert len(result) > 0
