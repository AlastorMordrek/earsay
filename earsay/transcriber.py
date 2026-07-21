from __future__ import annotations

import collections
import threading
import time
from typing import Optional

import numpy as np

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except OSError:
    HAS_SOUNDDEVICE = False


try:
    from faster_whisper import WhisperModel
    HAS_FASTER_WHISPER = True
except ImportError:
    HAS_FASTER_WHISPER = False


SAMPLE_RATE = 16000
BLOCK_SIZE = 512  # ~32ms at 16kHz
SILENCE_THRESHOLD = 0.015  # RMS energy threshold for silence
SILENCE_BLOCKS = 40  # ~1.3s of silence before utterance end
PRE_SPEECH_BUFFER_BLOCKS = 10  # keep 320ms before speech start


def _rms(block: np.ndarray) -> float:
    return float(np.sqrt(np.mean(block.astype(np.float64) ** 2)))


class Transcriber:
    def __init__(
        self,
        on_text: callable,
        model_name: str = "tiny.en",
        device: str = "auto",
        compute_type: str = "int8",
    ):
        if not HAS_SOUNDDEVICE:
            raise RuntimeError(
                "sounddevice not available. Install with: pip install sounddevice"
            )
        if not HAS_FASTER_WHISPER:
            raise RuntimeError(
                "faster-whisper not available. Install with: pip install faster-whisper"
            )

        self._on_text = on_text
        self._model_name = model_name
        self._model: Optional[WhisperModel] = None
        self._device = device
        self._compute_type = compute_type

        self._stream: Optional[sd.InputStream] = None
        self._running = False
        self._paused = False
        self._pause_cond = threading.Condition()

        self._ring: collections.deque = collections.deque(maxlen=600)  # ~20s
        self._in_speech = False
        self._silence_count = 0
        self._speech_buffer: list[np.ndarray] = []

        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._running:
            return
        if self._model is None:
            self._model = WhisperModel(
                self._model_name,
                device=self._device,
                compute_type=self._compute_type,
            )

        self._running = True
        self._thread = threading.Thread(target=self._audio_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False
        with self._pause_cond:
            self._pause_cond.notify_all()

    @property
    def is_paused(self) -> bool:
        return self._paused

    def _audio_loop(self) -> None:
        def callback(indata, frames, time_info, status):
            if status:
                return
            block = indata[:, 0].copy()
            self._ring.append(block)

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            blocksize=BLOCK_SIZE,
            callback=callback,
            dtype=np.float32,
        )
        self._stream.start()

        while self._running:
            if self._paused:
                with self._pause_cond:
                    self._pause_cond.wait(timeout=0.5)
                continue

            if len(self._ring) < BLOCK_SIZE:
                time.sleep(0.01)
                continue

            block = self._ring.popleft()
            energy = _rms(block)

            if self._in_speech:
                self._speech_buffer.append(block)
                if energy < SILENCE_THRESHOLD:
                    self._silence_count += 1
                    if self._silence_count >= SILENCE_BLOCKS:
                        self._end_utterance()
                else:
                    self._silence_count = 0
            else:
                self._speech_buffer.append(block)
                if energy >= SILENCE_THRESHOLD:
                    self._in_speech = True
                    self._silence_count = 0
                elif len(self._speech_buffer) > PRE_SPEECH_BUFFER_BLOCKS:
                    self._speech_buffer.pop(0)

        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass

    def _end_utterance(self) -> None:
        if not self._speech_buffer:
            self._in_speech = False
            self._silence_count = 0
            return

        audio = np.concatenate(self._speech_buffer)
        duration = len(audio) / SAMPLE_RATE

        self._speech_buffer = []
        self._in_speech = False
        self._silence_count = 0

        if duration < 0.3:
            return

        try:
            text = self._transcribe(audio)
            if text:
                self._on_text(text)
        except Exception:
            pass

    def _transcribe(self, audio: np.ndarray) -> str:
        segments, _ = self._model.transcribe(
            audio,
            language="en",
            beam_size=5,
            vad_filter=False,
        )
        parts = []
        for segment in segments:
            if segment.text:
                parts.append(segment.text.strip())
        return " ".join(parts)
