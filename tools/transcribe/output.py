"""Unified output format for transcription backends."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Word:
    word: str
    start: float
    end: float
    type: Optional[str] = None  # "filler" for um/uh, None for normal words


@dataclass
class Segment:
    id: int
    start: float
    end: float
    text: str
    words: list[Word] = field(default_factory=list)


@dataclass
class TranscriptMetadata:
    file: str
    duration_seconds: float
    backend: str
    language: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Transcript:
    metadata: TranscriptMetadata
    segments: list[Segment] = field(default_factory=list)

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        data = asdict(self)
        # Strip None values from words (type field)
        for seg in data["segments"]:
            seg["words"] = [
                {k: v for k, v in w.items() if v is not None}
                for w in seg["words"]
            ]
        return json.dumps(data, indent=indent)

    def save(self, path: str) -> None:
        """Write JSON to file."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())
