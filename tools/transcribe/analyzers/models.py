"""Data models for transcript analysis and cut list generation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class CutReason(str, Enum):
    FILLER = "filler"
    LONG_PAUSE = "long_pause"
    STAMMER = "stammer"
    FALSE_START = "false_start"
    RETAKE = "retake"
    HALLUCINATION = "hallucination"
    MISSPOKEN = "misspoken"
    ARTIFACT = "timestamp_artifact"
    SEMANTIC = "semantic"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Cut:
    start: float
    end: float
    reason: str
    confidence: str
    flagged_text: str
    context_before: str = ""
    context_after: str = ""
    explanation: str = ""
    source: str = "pass1"
    segment_ids: list[int] = field(default_factory=list)


@dataclass
class AnalysisConfig:
    pause_retake_threshold: float = 1.5
    pause_notable_threshold: float = 0.8
    stammer_max_distance: int = 1
    false_start_max_words: int = 5
    false_start_min_gap: float = 0.8
    hallucination_wps_threshold: float = 8.0
    artifact_word_duration: float = 3.0
    chunk_duration: float = 150.0
    overlap_segments: int = 2


@dataclass
class CutList:
    source_file: str
    duration_seconds: float
    config: AnalysisConfig
    cuts: list[Cut] = field(default_factory=list)
    pass1_stats: dict = field(default_factory=dict)
    pass2_stats: dict = field(default_factory=dict)

    def to_json(self, indent: int = 2) -> str:
        data = asdict(self)
        return json.dumps(data, indent=indent, ensure_ascii=False)

    def save_json(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())
