"""Tests for text processing pipeline components."""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestFillerRemover:
    """Tests for FillerRemover class."""

    def test_removes_common_fillers(self):
        """Should remove common filler words."""
        from whisper_dictation.text_processors import FillerRemover
        
        remover = FillerRemover()
        
        assert remover.process("um hello world") == "hello world"
        assert remover.process("uh I think so") == "I think so"
        assert remover.process("er let me see") == "let me see"

    def test_removes_repeated_fillers(self):
        """Should remove repeated filler sounds."""
        from whisper_dictation.text_processors import FillerRemover
        
        remover = FillerRemover()
        
        assert remover.process("umm hello") == "hello"
        assert remover.process("uhhh world") == "world"
        assert remover.process("hmmm yes") == "yes"

    def test_removes_phrase_fillers(self):
        """Should remove filler phrases."""
        from whisper_dictation.text_processors import FillerRemover
        
        remover = FillerRemover()
        
        result = remover.process("you know I think basically it works")
        assert "you know" not in result.lower()
        assert "basically" not in result.lower()

    def test_handles_empty_string(self):
        """Should handle empty string."""
        from whisper_dictation.text_processors import FillerRemover
        
        remover = FillerRemover()
        assert remover.process("") == ""

    def test_handles_no_fillers(self):
        """Should return unchanged text when no fillers present."""
        from whisper_dictation.text_processors import FillerRemover
        
        remover = FillerRemover()
        assert remover.process("Hello world") == "Hello world"

    def test_case_insensitive(self):
        """Should be case insensitive."""
        from whisper_dictation.text_processors import FillerRemover
        
        remover = FillerRemover()
        
        assert remover.process("UM hello") == "hello"
        assert remover.process("Um hello") == "hello"

    def test_cleans_multiple_spaces(self):
        """Should clean up multiple spaces after removal."""
        from whisper_dictation.text_processors import FillerRemover
        
        remover = FillerRemover()
        
        result = remover.process("hello um um world")
        assert "  " not in result


class TestSnippetExpander:
    """Tests for SnippetExpander class."""

    def test_expands_exact_match(self):
        """Should expand exact match snippets."""
        from whisper_dictation.text_processors import SnippetExpander
        
        snippets = {"signature": "Best regards,\nJohn Doe"}
        expander = SnippetExpander(snippets)
        
        assert expander.process("signature") == "Best regards,\nJohn Doe"

    def test_case_insensitive_match(self):
        """Should match case-insensitively."""
        from whisper_dictation.text_processors import SnippetExpander
        
        snippets = {"greeting": "Hello!"}
        expander = SnippetExpander(snippets)
        
        assert expander.process("GREETING") == "Hello!"
        assert expander.process("Greeting") == "Hello!"

    def test_insert_prefix_pattern(self):
        """Should handle 'insert X' pattern."""
        from whisper_dictation.text_processors import SnippetExpander
        
        snippets = {"address": "123 Main St"}
        expander = SnippetExpander(snippets)
        
        assert expander.process("insert address") == "123 Main St"

    def test_returns_unchanged_on_no_match(self):
        """Should return unchanged text when no snippet matches."""
        from whisper_dictation.text_processors import SnippetExpander
        
        snippets = {"greeting": "Hello!"}
        expander = SnippetExpander(snippets)
        
        assert expander.process("random text") == "random text"

    def test_handles_empty_string(self):
        """Should handle empty string."""
        from whisper_dictation.text_processors import SnippetExpander
        
        expander = SnippetExpander({})
        assert expander.process("") == ""

    def test_handles_empty_snippets(self):
        """Should work with empty snippets dict."""
        from whisper_dictation.text_processors import SnippetExpander
        
        expander = SnippetExpander({})
        assert expander.process("hello") == "hello"


class TestLanguageToolCorrector:
    """Tests for LanguageToolCorrector class."""

    def test_lazy_loading(self):
        """Should not load tool on initialization."""
        from whisper_dictation.grammar_corrector import LanguageToolCorrector
        
        corrector = LanguageToolCorrector()
        assert corrector._tool is None

    def test_handles_empty_string(self):
        """Should handle empty string without loading tool."""
        from whisper_dictation.grammar_corrector import LanguageToolCorrector
        from unittest.mock import patch, MagicMock
        
        mock_lt = MagicMock()
        
        with patch.dict(sys.modules, {'language_tool_python': mock_lt}):
            corrector = LanguageToolCorrector()
            result = corrector.correct("")
            
            assert result == ""
            mock_lt.LanguageTool.assert_not_called()

    def test_calls_tool_correct(self):
        """Should call tool.correct with text."""
        from whisper_dictation.grammar_corrector import LanguageToolCorrector
        from unittest.mock import patch, MagicMock
        
        mock_tool = MagicMock()
        mock_tool.correct.return_value = "He is here."
        mock_lt = MagicMock()
        mock_lt.LanguageTool.return_value = mock_tool
        
        with patch.dict(sys.modules, {'language_tool_python': mock_lt}):
            corrector = LanguageToolCorrector()
            result = corrector.correct("He are here.")
            
            assert result == "He is here."
            mock_tool.correct.assert_called_once_with("He are here.")

    def test_process_delegates_to_correct(self):
        """Should delegate process() to correct()."""
        from whisper_dictation.grammar_corrector import LanguageToolCorrector
        from unittest.mock import patch, MagicMock
        
        mock_tool = MagicMock()
        mock_tool.correct.return_value = "Fixed."
        mock_lt = MagicMock()
        mock_lt.LanguageTool.return_value = mock_tool
        
        with patch.dict(sys.modules, {'language_tool_python': mock_lt}):
            corrector = LanguageToolCorrector()
            result = corrector.process("Broken.")
            
            assert result == "Fixed."


class TestGramformerCorrector:
    """Tests for GramformerCorrector class."""

    def test_lazy_loading(self):
        """Should not load model on initialization."""
        from whisper_dictation.grammar_corrector import GramformerCorrector
        
        corrector = GramformerCorrector()
        assert corrector._model is None

    def test_handles_empty_string(self):
        """Should handle empty string without loading model."""
        from whisper_dictation.grammar_corrector import GramformerCorrector
        
        corrector = GramformerCorrector()
        result = corrector.correct("")
        
        assert result == ""
        assert corrector._model is None

    def test_handles_import_error(self):
        """Should handle missing gramformer gracefully."""
        from whisper_dictation.grammar_corrector import GramformerCorrector
        from unittest.mock import patch
        
        with patch.dict(sys.modules, {'gramformer': None}):
            corrector = GramformerCorrector()
            # Force load attempt
            corrector._model = None
            
            # Should not crash, should return original text
            result = corrector.correct("He are here.")
            # Will mark as unavailable or return original


class TestCreateGrammarCorrector:
    """Tests for create_grammar_corrector factory function."""

    def test_returns_none_for_none_engine(self):
        """Should return None when engine is None."""
        from whisper_dictation.grammar_corrector import create_grammar_corrector
        
        result = create_grammar_corrector(None)
        assert result is None

    def test_creates_languagetool_corrector(self):
        """Should create LanguageToolCorrector for 'languagetool'."""
        from whisper_dictation.grammar_corrector import create_grammar_corrector, LanguageToolCorrector
        
        result = create_grammar_corrector("languagetool", "en")
        assert isinstance(result, LanguageToolCorrector)

    def test_creates_gramformer_corrector(self):
        """Should create GramformerCorrector for 'gramformer'."""
        from whisper_dictation.grammar_corrector import create_grammar_corrector, GramformerCorrector
        
        result = create_grammar_corrector("gramformer")
        assert isinstance(result, GramformerCorrector)

    def test_case_insensitive_engine_name(self):
        """Should handle engine name case-insensitively."""
        from whisper_dictation.grammar_corrector import create_grammar_corrector, LanguageToolCorrector
        
        result = create_grammar_corrector("LanguageTool", "en")
        assert isinstance(result, LanguageToolCorrector)

    def test_returns_none_for_unknown_engine(self):
        """Should return None for unknown engine."""
        from whisper_dictation.grammar_corrector import create_grammar_corrector
        
        result = create_grammar_corrector("unknown_engine")
        assert result is None


class TestWordCorrector:
    def test_replaces_misheard_variants_case_insensitively(self):
        from whisper_dictation.text_processors import WordCorrector

        c = WordCorrector({"kraxam": "Kragzam", "craxam": "Kragzam"})
        assert c.process("I use Kraxam and craxam.") == "I use Kragzam and Kragzam."

    def test_matches_whole_words_only(self):
        from whisper_dictation.text_processors import WordCorrector

        assert WordCorrector({"cat": "dog"}).process("concat cat") == "concat dog"

    def test_multi_word_and_empty(self):
        from whisper_dictation.text_processors import WordCorrector

        c = WordCorrector({"crag zam": "Kragzam"})
        assert c.process("try crag zam now") == "try Kragzam now"
        assert WordCorrector({}).process("hi") == "hi"


class TestDictionaryParsing:
    def test_parse_and_errors(self):
        import pytest
        from whisper_dictation.config import DictationConfig

        assert DictationConfig.parse_dictionary("Kraxam=Kragzam, a=B") == {
            "kraxam": "Kragzam", "a": "B"}
        assert DictationConfig.parse_dictionary("") == {}
        with pytest.raises(ValueError):
            DictationConfig.parse_dictionary("nonsense")

    def test_dictionary_not_persisted_in_json(self):
        from whisper_dictation.config import DictationConfig

        c = DictationConfig(dictionary={"kraxam": "Kragzam"})
        assert "dictionary" not in c.to_json_dict()

    def test_reload_dictionary_from_file(self, tmp_path):
        from whisper_dictation.config import DictationConfig

        f = tmp_path / "words.txt"
        f.write_text("# comment\nkraxam=Kragzam\ncrag zam=Kragzam\n")
        c = DictationConfig(dictionary_path=str(f))
        c.reload_dictionary()
        assert c.dictionary == {"kraxam": "Kragzam", "crag zam": "Kragzam"}
        f.write_text("foo=Bar\n")
        c.reload_dictionary()
        assert c.dictionary == {"foo": "Bar"}

    def test_reload_dictionary_strict_raises_on_bad_entry(self, tmp_path):
        import pytest
        from whisper_dictation.config import DictationConfig

        f = tmp_path / "words.txt"
        f.write_text("nonsense\n")
        c = DictationConfig(dictionary_path=str(f))
        with pytest.raises(ValueError):
            c.reload_dictionary(strict=True)

    def test_ensure_dictionary_file_creates_template(self, tmp_path):
        from whisper_dictation.config import DictationConfig, ensure_dictionary_file

        path = ensure_dictionary_file(str(tmp_path / "sub" / "d.txt"))
        assert path.exists()
        assert DictationConfig.parse_dictionary(path.read_text()) == {}
