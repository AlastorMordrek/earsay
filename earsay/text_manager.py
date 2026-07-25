from __future__ import annotations

import asyncio
import sys
import threading
import time
import uuid
from typing import Callable, Optional

from earsay.models import Checkpoint, NewText, SubscriptionEvent, SubscriptionRequest


class Subscription:
    def __init__(self, req: SubscriptionRequest):
        self.ticket = req.ticket
        self.chars_threshold = req.chars
        self.timeout_ms = req.timeout_ms
        self.fullchunk = req.fullchunk
        self.last_sent_pos = 0
        self.last_activity = time.monotonic()
        self.event_queue: asyncio.Queue[Optional[SubscriptionEvent]] = asyncio.Queue()


class TextManager:
    def __init__(self, on_append: Optional[Callable[[str], None]] = None):
        self._lock = threading.Lock()
        self._buffer: str = ""
        self._checkpoints: list[tuple[int, int]] = []  # [(index, position)]
        self._subscriptions: dict[str, Subscription] = {}
        self._started_at = time.monotonic()
        self._on_append = on_append
        self._loop: asyncio.AbstractEventLoop | None = None

    def append(self, text: str) -> None:
        if not text:
            return
        with self._lock:
            self._buffer += text
        if self._on_append:
            self._on_append(text)

        subscriptions = self._subscriptions_snapshot()
        for sub in subscriptions:
            for event in self._should_trigger(sub):
                self._push_event_threadsafe(sub, event)

    def _subscriptions_snapshot(self) -> list[Subscription]:
        with self._lock:
            return list(self._subscriptions.values())

    def _should_trigger(self, sub: Subscription) -> list[SubscriptionEvent]:
        events: list[SubscriptionEvent] = []
        with self._lock:
            sub.last_activity = time.monotonic()
            idx = len(self._checkpoints)
            while True:
                new_chars = len(self._buffer) - sub.last_sent_pos
                if new_chars < sub.chars_threshold:
                    break
                emit_len = min(new_chars, sub.chars_threshold)
                emit_text = self._buffer[
                    sub.last_sent_pos : sub.last_sent_pos + emit_len
                ]
                sub.last_sent_pos += len(emit_text)
                events.append(
                    SubscriptionEvent(
                        ticket=sub.ticket,
                        potential_index=idx,
                        text=emit_text,
                        trigger="chars",
                    )
                )
        return events

    def fire_timeout_subscriptions(self) -> None:
        now = time.monotonic()
        subscriptions = self._subscriptions_snapshot()
        for sub in subscriptions:
            elapsed_ms = (now - sub.last_activity) * 1000
            if elapsed_ms >= sub.timeout_ms:
                with self._lock:
                    new_chars = len(self._buffer) - sub.last_sent_pos
                    text = self._buffer[sub.last_sent_pos :]
                    sub.last_sent_pos = len(self._buffer)
                    sub.last_activity = now
                idx = len(self._checkpoints)
                event = SubscriptionEvent(
                    ticket=sub.ticket,
                    potential_index=idx,
                    text=text,
                    trigger="timeout",
                )
                # only log non-empty events to avoid noise
                if text:
                    print(
                        f"[earsay] timeout push text={text!r}",
                        file=sys.stderr,
                        flush=True,
                    )
                self._push_event(sub, event)

    def _push_event(self, sub: Subscription, event: SubscriptionEvent) -> None:
        try:
            sub.event_queue.put_nowait(event)
        except asyncio.QueueFull:
            pass

    def _push_event_threadsafe(
        self, sub: Subscription, event: SubscriptionEvent
    ) -> None:
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(sub.event_queue.put_nowait, event)

    def all_text(self) -> str:
        with self._lock:
            return self._buffer

    def new_text(self) -> NewText:
        with self._lock:
            last_pos = self._last_checkpoint_position()
            text = self._buffer[last_pos:]
            return NewText(potential_index=len(self._checkpoints), text=text)

    def set_checkpoint(self, at: Optional[int] = None) -> Checkpoint:
        with self._lock:
            if at is None:
                at = len(self._buffer)
            elif at <= 0:
                raise ValueError("Checkpoint position must be positive")
            elif self._checkpoints:
                last_pos = self._checkpoints[-1][1]
                if at <= last_pos:
                    raise ValueError(
                        f"Cannot create checkpoint at {at}: must be after "
                        f"last checkpoint position {last_pos}"
                    )

            if at > len(self._buffer):
                at = len(self._buffer)

            idx = len(self._checkpoints)
            self._checkpoints.append((idx, at))

            return self._checkpoint_text(idx)

    def re_checkpoint(self, at: int) -> Checkpoint:
        with self._lock:
            if not self._checkpoints:
                raise ValueError("No checkpoints to re-define")

            idx = len(self._checkpoints) - 1

            if idx > 0 and at <= self._checkpoints[idx - 1][1]:
                raise ValueError(
                    f"Cannot re-checkpoint at {at}: must be after "
                    f"previous checkpoint at {self._checkpoints[idx - 1][1]}"
                )
            if at <= 0:
                raise ValueError("Checkpoint position must be positive")
            if at > len(self._buffer):
                at = len(self._buffer)

            self._checkpoints[idx] = (idx, at)
            return self._checkpoint_text(idx)

    def _checkpoint_text(self, idx: int) -> Checkpoint:
        _, pos = self._checkpoints[idx]
        start = 0 if idx == 0 else self._checkpoints[idx - 1][1]
        text = self._buffer[start:pos]
        return Checkpoint(index=idx, position=pos, text=text)

    def _last_checkpoint_position(self) -> int:
        if self._checkpoints:
            return self._checkpoints[-1][1]
        return 0

    def add_subscription(self, req: SubscriptionRequest) -> Subscription:
        with self._lock:
            sub = Subscription(req)
            sub.last_sent_pos = len(self._buffer)
            sub.last_activity = time.monotonic()
            self._subscriptions[sub.ticket] = sub
            return sub

    def remove_subscription(self, ticket: str) -> bool:
        with self._lock:
            if ticket in self._subscriptions:
                sub = self._subscriptions.pop(ticket)
                sub.event_queue.put_nowait(None)
                return True
            return False

    @property
    def status(self):
        uptime = time.monotonic() - self._started_at
        with self._lock:
            return dict(
                chars_transcribed=len(self._buffer),
                checkpoint_count=len(self._checkpoints),
                subscription_count=len(self._subscriptions),
                uptime_seconds=round(uptime, 1),
            )

    def subscription_count(self) -> int:
        with self._lock:
            return len(self._subscriptions)
