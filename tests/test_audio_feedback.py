"""Tests for AudioFeedback class."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAudioFeedbackInit:
    """Tests for AudioFeedback initialization."""

    def test_default_enabled(self):
        """Should be enabled by default."""
        from whisper_dictation.audio_feedback import AudioFeedback
        
        feedback = AudioFeedback()
        assert feedback.enabled is True

    def test_can_disable(self):
        """Should be able to disable."""
        from whisper_dictation.audio_feedback import AudioFeedback
        
        feedback = AudioFeedback(enabled=False)
        assert feedback.enabled is False


class TestAudioFeedbackPlayStart:
    """Tests for play_start method."""

    def test_plays_when_enabled(self):
        """Should play sound when enabled."""
        from whisper_dictation.audio_feedback import AudioFeedback
        
        with patch('subprocess.Popen') as mock_popen:
            feedback = AudioFeedback(enabled=True)
            feedback.play_start()
            
            mock_popen.assert_called_once()

    def test_silent_when_disabled(self):
        """Should not play sound when disabled."""
        from whisper_dictation.audio_feedback import AudioFeedback
        
        with patch('subprocess.Popen') as mock_popen:
            feedback = AudioFeedback(enabled=False)
            feedback.play_start()
            
            mock_popen.assert_not_called()

    def test_handles_subprocess_error(self):
        """Should handle subprocess errors gracefully."""
        from whisper_dictation.audio_feedback import AudioFeedback
        
        with patch('subprocess.Popen', side_effect=Exception("Audio failed")):
            feedback = AudioFeedback(enabled=True)
            # Should not raise exception
            feedback.play_start()


class TestAudioFeedbackPlayStop:
    """Tests for play_stop method."""

    def test_plays_when_enabled(self):
        """Should play sound when enabled."""
        from whisper_dictation.audio_feedback import AudioFeedback
        
        with patch('subprocess.Popen') as mock_popen:
            feedback = AudioFeedback(enabled=True)
            feedback.play_stop()
            
            mock_popen.assert_called_once()

    def test_silent_when_disabled(self):
        """Should not play sound when disabled."""
        from whisper_dictation.audio_feedback import AudioFeedback
        
        with patch('subprocess.Popen') as mock_popen:
            feedback = AudioFeedback(enabled=False)
            feedback.play_stop()
            
            mock_popen.assert_not_called()

    def test_handles_subprocess_error(self):
        """Should handle subprocess errors gracefully."""
        from whisper_dictation.audio_feedback import AudioFeedback
        
        with patch('subprocess.Popen', side_effect=Exception("Audio failed")):
            feedback = AudioFeedback(enabled=True)
            # Should not raise exception
            feedback.play_stop()


class TestAudioFeedbackBeep:
    """Tests for _play_beep method."""

    def test_uses_system_sound(self):
        """Should use macOS system sound."""
        from whisper_dictation.audio_feedback import AudioFeedback
        
        with patch('subprocess.Popen') as mock_popen:
            feedback = AudioFeedback(enabled=True)
            feedback._play_beep(800, 0.1)
            
            # Should call afplay with a system sound
            call_args = mock_popen.call_args
            assert call_args[0][0][0] == "afplay"
            assert "Tink.aiff" in call_args[0][0][1]

    def test_does_not_block_caller(self):
        """Should fire and forget: never wait for the sound to finish.

        Blocking here would stall the keyboard event-tap callback and make
        macOS disable the hotkey.
        """
        from whisper_dictation.audio_feedback import AudioFeedback
        
        with patch('subprocess.Popen') as mock_popen:
            feedback = AudioFeedback(enabled=True)
            feedback._play_beep(800, 0.1)
            
            proc = mock_popen.return_value
            proc.wait.assert_not_called()
            proc.communicate.assert_not_called()

    def test_discards_output(self):
        """Should discard subprocess output instead of filling a pipe."""
        from whisper_dictation.audio_feedback import AudioFeedback
        import subprocess
        
        with patch('subprocess.Popen') as mock_popen:
            feedback = AudioFeedback(enabled=True)
            feedback._play_beep(800, 0.1)
            
            call_kwargs = mock_popen.call_args[1]
            assert call_kwargs['stdout'] == subprocess.DEVNULL
            assert call_kwargs['stderr'] == subprocess.DEVNULL

    def test_start_and_stop_use_different_sounds(self):
        """Start and stop must be audibly distinguishable."""
        from whisper_dictation.audio_feedback import AudioFeedback
        
        with patch('subprocess.Popen') as mock_popen:
            feedback = AudioFeedback(enabled=True)
            feedback.play_start()
            feedback.play_stop()
            
            sounds = [call[0][0][1] for call in mock_popen.call_args_list]
            assert len(sounds) == 2
            assert sounds[0] != sounds[1]

    def test_handles_spawn_error(self):
        """Should handle process spawn errors gracefully."""
        from whisper_dictation.audio_feedback import AudioFeedback
        
        with patch('subprocess.Popen', side_effect=OSError("cannot spawn")):
            feedback = AudioFeedback(enabled=True)
            # Should not raise exception
            feedback._play_beep(800, 0.1)

    def test_handles_file_not_found(self):
        """Should handle missing sound file gracefully."""
        from whisper_dictation.audio_feedback import AudioFeedback
        
        with patch('subprocess.Popen', side_effect=FileNotFoundError("Sound not found")):
            feedback = AudioFeedback(enabled=True)
            # Should not raise exception
            feedback._play_beep(800, 0.1)
