from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Checkpoint:
    index: int
    position: int
    text: str


@dataclass
class NewText:
    potential_index: int
    text: str


@dataclass
class SubscriptionEvent:
    ticket: str
    potential_index: int
    text: str


@dataclass
class Status:
    status: str  # "listening" | "paused" | "stopped"
    uptime_seconds: float
    chars_transcribed: int
    checkpoint_count: int
    subscription_count: int
    port: Optional[int] = None


@dataclass
class PidFile:
    port: int
    pid: int
    started_at: str


@dataclass
class SubscriptionRequest:
    ticket: str = field(default_factory=lambda: str(uuid.uuid4()))
    chars: int = 30
    timeout_ms: int = 3000
    fullchunk: bool = False
