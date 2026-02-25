"""OpenAI Whisper API backend for transcription."""

from __future__ import annotations

import os
from pathlib import Path

from openai import OpenAI

from tools.transcribe.output import Transcript, TranscriptMetadata, Segment, Word

# OpenAI Whisper API file size limit
_MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB


def transcribe(audio_path: str, language: str = "en") -> Transcript:
    """Transcribe audio using OpenAI Whisper API with word+segment timestamps."""
    # Validate file size
    file_size = os.path.getsize(audio_path)
    if file_size > _MAX_FILE_SIZE:
        raise ValueError(
            f"File is {file_size / 1024 / 1024:.1f}MB, exceeds OpenAI's 25MB limit. "
            f"Convert to a compressed format (mp3/ogg) or use --local."
        )

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY environment variable is not set. "
            "Set it or use --local for CrisperWhisper."
        )

    client = OpenAI()

    with open(audio_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            file=audio_file,
            model="whisper-1",
            response_format="verbose_json",
            timestamp_granularities=["word", "segment"],
            language=language,
        )

    raw_segments = response.segments or []
    raw_words = response.words or []

    # Build segments with word-level timestamps
    if not raw_segments and raw_words:
        # Fallback: API returned words but no segments — build a single segment
        all_words = [
            Word(word=w.word.strip(), start=w.start, end=w.end)
            for w in raw_words
        ]
        segments = [Segment(
            id=0,
            start=raw_words[0].start,
            end=raw_words[-1].end,
            text=response.text.strip(),
            words=all_words,
        )]
    elif raw_segments:
        words_by_segment = _assign_words_to_segments(raw_segments, raw_words)
        segments = []
        for i, seg in enumerate(raw_segments):
            seg_words = [
                Word(word=w.word.strip(), start=w.start, end=w.end)
                for w in words_by_segment.get(i, [])
            ]
            segments.append(Segment(
                id=i,
                start=seg.start,
                end=seg.end,
                text=seg.text.strip(),
                words=seg_words,
            ))
    else:
        # No segments and no words — empty transcript
        segments = []

    metadata = TranscriptMetadata(
        file=Path(audio_path).name,
        duration_seconds=response.duration,
        backend="openai_whisper",
        language=language,
    )

    return Transcript(metadata=metadata, segments=segments)


def _assign_words_to_segments(segments, words):
    """Map words to their containing segment by midpoint overlap."""
    if not segments or not words:
        return {}

    result = {i: [] for i in range(len(segments))}
    for w in words:
        midpoint = (w.start + w.end) / 2
        assigned = False
        for i, seg in enumerate(segments):
            if seg.start <= midpoint <= seg.end:
                result[i].append(w)
                assigned = True
                break
        if not assigned:
            # Word doesn't fit any segment — assign to nearest
            nearest = min(range(len(segments)), key=lambda j: abs(segments[j].start - w.start))
            result[nearest].append(w)
    return result
