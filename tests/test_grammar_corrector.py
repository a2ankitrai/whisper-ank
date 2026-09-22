"""Tests for GrammarCorrector classes (legacy compatibility tests)."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys


class TestGrammarCorrectorInit:
    """Tests for LanguageToolCorrector initialization (legacy GrammarCorrector tests)."""

    def test_default_language(self):
        """Test default language is en-US."""
        from whisper_dictation.grammar_corrector import LanguageToolCorrector
        
        corrector = LanguageToolCorrector()
        assert corrector.language == "en-US"
    
    def test_custom_language(self):
        """Test custom language setting."""
        from whisper_dictation.grammar_corrector import LanguageToolCorrector
        
        corrector = LanguageToolCorrector(language="de-DE")
        assert corrector.language == "de-DE"
    
    def test_tool_not_loaded_initially(self):
        """Test that LanguageTool is not loaded on init (lazy loading)."""
        from whisper_dictation.grammar_corrector import LanguageToolCorrector
        
        corrector = LanguageToolCorrector()
        assert corrector._tool is None


class TestGrammarCorrectorLazyLoading:
    """Tests for lazy loading behavior."""

    def test_loads_tool_on_first_correct_call(self):
        """Test that tool is loaded on first correct() call."""
        from whisper_dictation.grammar_corrector import LanguageToolCorrector
        
        mock_tool = MagicMock()
        mock_tool.correct.return_value = "Corrected text."
        mock_lt_module = MagicMock()
        mock_lt_module.LanguageTool.return_value = mock_tool
        
        with patch.dict(sys.modules, {'language_tool_python': mock_lt_module}):
            corrector = LanguageToolCorrector()
            assert corrector._tool is None
            
            corrector.correct("Some text")
            
            mock_lt_module.LanguageTool.assert_called_once_with("en-US")
            assert corrector._tool is mock_tool

    def test_does_not_reload_on_subsequent_calls(self):
        """Test that tool is not reloaded on subsequent correct() calls."""
        from whisper_dictation.grammar_corrector import LanguageToolCorrector
        
        mock_tool = MagicMock()
        mock_tool.correct.return_value = "Corrected."
        mock_lt_module = MagicMock()
        mock_lt_module.LanguageTool.return_value = mock_tool
        
        with patch.dict(sys.modules, {'language_tool_python': mock_lt_module}):
            corrector = LanguageToolCorrector()
            corrector.correct("First call")
            corrector.correct("Second call")
            corrector.correct("Third call")
            
            # Should only be called once despite multiple correct() calls
            mock_lt_module.LanguageTool.assert_called_once()


class TestGrammarCorrectorCorrect:
    """Tests for the correct() method."""

    def test_returns_corrected_text(self):
        """Test that correct() returns the corrected text."""
        from whisper_dictation.grammar_corrector import LanguageToolCorrector
        
        mock_tool = MagicMock()
        mock_tool.correct.return_value = "Hello, world."
        mock_lt_module = MagicMock()
        mock_lt_module.LanguageTool.return_value = mock_tool
        
        with patch.dict(sys.modules, {'language_tool_python': mock_lt_module}):
            corrector = LanguageToolCorrector()
            result = corrector.correct("hello world")
            
            assert result == "Hello, world."
            mock_tool.correct.assert_called_once_with("hello world")

    def test_handles_empty_string(self):
        """Test that empty string returns empty without loading tool."""
        from whisper_dictation.grammar_corrector import LanguageToolCorrector
        
        mock_lt_module = MagicMock()
        
        with patch.dict(sys.modules, {'language_tool_python': mock_lt_module}):
            corrector = LanguageToolCorrector()
            result = corrector.correct("")
            
            assert result == ""
            mock_lt_module.LanguageTool.assert_not_called()

    def test_preserves_already_correct_text(self):
        """Test that already correct text is returned unchanged."""
        from whisper_dictation.grammar_corrector import LanguageToolCorrector
        
        mock_tool = MagicMock()
        mock_tool.correct.return_value = "This is correct."
        mock_lt_module = MagicMock()
        mock_lt_module.LanguageTool.return_value = mock_tool
        
        with patch.dict(sys.modules, {'language_tool_python': mock_lt_module}):
            corrector = LanguageToolCorrector()
            result = corrector.correct("This is correct.")
            
            assert result == "This is correct."


class TestDictationAppGrammarIntegration:
    """Tests for grammar correction integration in DictationApp."""

    @patch('whisper_dictation.dictation_app.Transcriber')
    @patch('whisper_dictation.dictation_app.AudioRecorder')
    @patch('whisper_dictation.dictation_app.TextTyper')
    @patch('whisper_dictation.dictation_app.AudioFeedback')
    def test_grammar_disabled_by_default(self, mock_feedback, mock_typer, mock_recorder, mock_transcriber):
        """Test that grammar correction is disabled by default."""
        from whisper_dictation.dictation_app import DictationApp
        
        app = DictationApp()
        
        assert app.enable_grammar is False
        assert app.grammar_corrector is None

    @patch('whisper_dictation.dictation_app.Transcriber')
    @patch('whisper_dictation.dictation_app.AudioRecorder')
    @patch('whisper_dictation.dictation_app.TextTyper')
    @patch('whisper_dictation.dictation_app.AudioFeedback')
    def test_grammar_can_be_enabled(self, mock_feedback, mock_typer, mock_recorder, mock_transcriber):
        """Test that grammar correction can be enabled."""
        from whisper_dictation.dictation_app import DictationApp
        
        app = DictationApp(enable_grammar=True)
        
        assert app.enable_grammar is True
        assert app.grammar_corrector is not None

    @patch('whisper_dictation.dictation_app.Transcriber')
    @patch('whisper_dictation.dictation_app.AudioRecorder')
    @patch('whisper_dictation.dictation_app.TextTyper')
    @patch('whisper_dictation.dictation_app.AudioFeedback')
    def test_grammar_corrector_in_processors(self, mock_feedback, mock_typer, mock_recorder, mock_transcriber):
        """Test that grammar corrector is added to processors when enabled."""
        from whisper_dictation.dictation_app import DictationApp
        from whisper_dictation.grammar_corrector import LanguageToolCorrector
        
        app = DictationApp(enable_grammar=True)
        
        # Check that a grammar corrector is in the processors list
        grammar_processors = [p for p in app.processors if isinstance(p, LanguageToolCorrector)]
        assert len(grammar_processors) == 1
