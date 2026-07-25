from __future__ import annotations

import collections
import sys
import threading
import time
from typing import Optional

import numpy as np

SAMPLE_RATE = 16000
BLOCK_SIZE = 512
DEFAULT_SILENCE_THRESHOLD = 0.015
SILENCE_BLOCKS = 15
PRE_SPEECH_BUFFER_BLOCKS = 10
CALIBRATION_SECONDS = 2.0
MAX_UTTERANCE_SECONDS = 3.0


def _rms(block: np.ndarray) -> float:
    return float(np.sqrt(np.mean(block.astype(np.float64) ** 2)))


def warmup() -> None:
    """Pre-load all heavy dependencies to avoid cold-start delays later.

    Call this in scripts or CI before running ``earsay listen`` so that
    the actual transcription starts instantly. Without it, the first
    invocation of listen incurs a 15-30 second import cost on macOS.
    """
    import sounddevice as sd
    from faster_whisper import WhisperModel

    _ = sd.query_devices()
    _ = WhisperModel


class Transcriber:
    def __init__(
        self,
        on_text: callable,
        model_name: str = "tiny.en",
        device: str = "auto",
        compute_type: str = "int8",
    ):
        self._on_text = on_text
        self._model_name = model_name
        self._model = None
        self._device = device
        self._compute_type = compute_type

        self._stream = None
        self._running = False
        self._paused = False
        self._pause_cond = threading.Condition()

        self._ring: collections.deque = collections.deque(maxlen=600)
        self._in_speech = False
        self._silence_count = 0
        self._speech_buffer: list[np.ndarray] = []

        self._calibrated = False
        self._threshold = DEFAULT_SILENCE_THRESHOLD
        self._calibration_samples: list[float] = []
        self._calibration_blocks = int(SAMPLE_RATE * CALIBRATION_SECONDS / BLOCK_SIZE)

        self._utterance_start: float = 0.0

        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._running:
            return
        if self._model is None:
            from faster_whisper import WhisperModel

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
        import sounddevice as sd

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

            if len(self._ring) < 1:
                time.sleep(0.01)
                continue

            block = self._ring.popleft()
            energy = _rms(block)

            if not self._calibrated:
                self._calibration_samples.append(energy)
                if len(self._calibration_samples) >= self._calibration_blocks:
                    median_noise = float(np.median(self._calibration_samples))
                    self._threshold = max(median_noise * 3.0, 0.005)
                    self._calibrated = True
                    print(
                        f"[earsay] noise floor: {median_noise:.6f}  "
                        f"threshold: {self._threshold:.6f}",
                        file=sys.stderr,
                        flush=True,
                    )
                else:
                    continue

            if self._in_speech and (
                time.time() - self._utterance_start > MAX_UTTERANCE_SECONDS
            ):
                self._end_utterance()
                continue

            if self._in_speech:
                self._speech_buffer.append(block)
                if energy < self._threshold:
                    self._silence_count += 1
                    if self._silence_count >= SILENCE_BLOCKS:
                        self._end_utterance()
                else:
                    self._silence_count = 0
            else:
                self._speech_buffer.append(block)
                if energy >= self._threshold:
                    self._in_speech = True
                    self._utterance_start = time.time()
                    self._silence_count = 0
                elif len(self._speech_buffer) > PRE_SPEECH_BUFFER_BLOCKS:
                    self._speech_buffer.pop(0)

        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass

    @staticmethod
    def _is_noise_only(text: str) -> bool:
        text = (
            text.strip()
            .replace(".", "")
            .replace("?", "")
            .replace("!", "")
            .replace(",", "")
            .replace(" ", "")
            .replace("\u2026", "")
        )
        return len(text) == 0

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
            if text and not self._is_noise_only(text):
                self._on_text(text)
        except Exception:
            pass

    def _transcribe(self, audio: np.ndarray) -> str:
        segments, _ = self._model.transcribe(
            audio,
            language="en",
            beam_size=5,
            vad_filter=True,
        )
        parts = []
        for segment in segments:
            if segment.text:
                parts.append(segment.text.strip())
        return " ".join(parts)
