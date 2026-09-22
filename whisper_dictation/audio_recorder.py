"""Audio recording from the microphone."""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd


class AudioRecorder:
    """Records audio from the microphone.

    The input stream is opened once and kept open for the lifetime of the app.
    Opening/closing a CoreAudio stream for every dictation is what used to
    deadlock inside PortAudio (`sounddevice.abort()` never returning), which
    wedged the hotkey and left the microphone dead until a restart. Starting
    and stopping a recording is now just a flag flip, which also means no
    audio is lost while the device spins up.
    """

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.recording = False
        self.audio_chunks: list[np.ndarray] = []
        self.stream = None
        self.lock = threading.Lock()

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"⚠️  Audio status: {status}", file=sys.stderr)
        # Grab the buffer *before* re-checking the flag and never take the
        # lock here: this runs on PortAudio's real-time thread. Reading in
        # this order means a callback that races with stop() appends to the
        # list that was just swapped out (and discarded) instead of leaking
        # audio into the next recording.
        chunks = self.audio_chunks
        if self.recording:
            chunks.append(indata.copy())

    def _ensure_stream(self):
        """Open the shared input stream, or replace it if it died."""
        stream = self.stream
        if stream is not None:
            try:
                if stream.active:
                    return
            except Exception:
                pass
            # Dead stream (device unplugged, sample rate changed...): drop it
            # in the background, since closing it may block.
            self.stream = None
            self._close_stream(stream)

        stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=self._audio_callback,
        )
        stream.start()
        self.stream = stream

    def start(self):
        """Start capturing audio into the buffer."""
        with self.lock:
            self.audio_chunks = []
            self.recording = True

        try:
            self._ensure_stream()
        except Exception:
            with self.lock:
                self.recording = False
            raise

    def stop(self) -> np.ndarray | None:
        """Stop capturing and return the recorded audio.

        The stream deliberately stays open; see the class docstring.
        """
        with self.lock:
            self.recording = False
            chunks, self.audio_chunks = self.audio_chunks, []

        if not chunks:
            return None

        audio = np.concatenate(chunks, axis=0).flatten()
        return audio

    def close(self):
        """Release the microphone (called on shutdown)."""
        with self.lock:
            self.recording = False
        stream, self.stream = self.stream, None
        if stream is not None and not self._close_stream(stream):
            print(
                "⚠️  Audio device did not release in time, continuing anyway",
                file=sys.stderr,
            )

    @staticmethod
    def _close_stream(stream, timeout: float = 2.0) -> bool:
        """Abort and close a stream, giving up after `timeout` seconds.

        PortAudio can block forever here, so it never runs on a thread we
        care about.
        """

        def closer():
            try:
                stream.abort()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass

        thread = threading.Thread(target=closer, daemon=True)
        thread.start()
        thread.join(timeout)
        return not thread.is_alive()

    def save_wav(self, audio: np.ndarray, path: Path):
        """Save audio to WAV file.

        Samples are clipped before the int16 conversion; without that, a
        loud passage above 1.0 would wrap around and turn into noise that
        Whisper cannot transcribe.
        """
        import wave

        audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_int16.tobytes())
