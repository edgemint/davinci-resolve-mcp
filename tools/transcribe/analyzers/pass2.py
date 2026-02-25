"""Pass 2: chunked semantic analysis for transcript cut list generation.

This module is responsible for:
  - Splitting a transcript into overlapping time-based chunks
  - Building LLM prompts for each chunk
  - Parsing LLM responses back into Cut objects

It does NOT make LLM calls. The orchestration layer is responsible for
dispatching each chunk prompt and feeding the responses to parse_chunk_response.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Transcript types live one level up in the transcribe package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from output import Segment, Transcript  # noqa: E402

from .models import AnalysisConfig, Confidence, Cut, CutReason  # noqa: E402

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    """A time-bounded slice of a transcript prepared for LLM analysis."""

    chunk_id: int
    start_time: float
    end_time: float
    segments: list[Segment]
    overlap_before: list[Segment] = field(default_factory=list)
    overlap_after: list[Segment] = field(default_factory=list)
    pass1_cuts_in_range: list[Cut] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def format_timecode(seconds: float) -> str:
    """Format seconds as MM:SS.ss  (e.g. 683.45 -> '11:23.45')."""
    minutes = int(seconds // 60)
    secs = seconds - minutes * 60
    return f"{minutes:02d}:{secs:05.2f}"


def _cuts_in_range(cuts: list[Cut], start: float, end: float) -> list[Cut]:
    """Return cuts whose midpoint falls within [start, end)."""
    return [c for c in cuts if start <= (c.start + c.end) / 2.0 < end]


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_transcript(
    transcript: Transcript,
    config: AnalysisConfig,
    pass1_cuts: list[Cut],
) -> list[Chunk]:
    """Split *transcript* into overlapping time-based chunks.

    Algorithm
    ---------
    1. Walk segments, accumulating until elapsed duration >= config.chunk_duration.
    2. Always split on a segment boundary (never mid-segment).
    3. Attach config.overlap_segments segments from the previous/next chunk as
       context so the LLM can reason across chunk borders.
    4. Attach Pass 1 cuts whose midpoint falls inside each chunk's time range.

    Returns
    -------
    list[Chunk]
        Ordered list of non-overlapping chunks (overlap segments are metadata
        only and are not double-counted across chunk IDs).
    """
    segments = transcript.segments
    if not segments:
        return []

    # --- Build raw slice boundaries (indices into segments list) ---
    slice_starts: list[int] = [0]
    chunk_start_time = segments[0].start

    for i, seg in enumerate(segments):
        elapsed = seg.end - chunk_start_time
        if elapsed >= config.chunk_duration and i + 1 < len(segments):
            # Split *after* this segment; next chunk begins at i+1.
            slice_starts.append(i + 1)
            chunk_start_time = segments[i + 1].start

    # Build (start_idx, end_idx) pairs — end_idx is exclusive.
    boundaries: list[tuple[int, int]] = []
    for j, start_idx in enumerate(slice_starts):
        end_idx = slice_starts[j + 1] if j + 1 < len(slice_starts) else len(segments)
        boundaries.append((start_idx, end_idx))

    # --- Construct Chunk objects ---
    chunks: list[Chunk] = []
    overlap_n = config.overlap_segments

    for chunk_id, (start_idx, end_idx) in enumerate(boundaries):
        core_segs = segments[start_idx:end_idx]

        # Overlap: borrow segments from adjacent slices.
        overlap_before = segments[max(0, start_idx - overlap_n):start_idx]
        overlap_after = segments[end_idx:end_idx + overlap_n]

        chunk_start = core_segs[0].start
        chunk_end = core_segs[-1].end

        relevant_cuts = _cuts_in_range(pass1_cuts, chunk_start, chunk_end)

        chunks.append(Chunk(
            chunk_id=chunk_id,
            start_time=chunk_start,
            end_time=chunk_end,
            segments=core_segs,
            overlap_before=overlap_before,
            overlap_after=overlap_after,
            pass1_cuts_in_range=relevant_cuts,
        ))

    return chunks


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

_REASON_DESCRIPTIONS = """\
- REPEATED_TAKE   : The same idea or sentence is expressed twice in a row with
                    different wording. Flag the FIRST attempt; keep the second
                    (usually cleaner) version. Include both in start/end range.
- ABANDONED       : Speaker starts a thought, trails off or stops mid-sentence,
                    then restarts differently. Flag the abandoned fragment only.
- MISSPOKEN       : A word that does not fit the context (wrong word, malapropism,
                    accidental substitution). Flag for human review — do NOT
                    automatically decide to cut.
- INCOHERENT      : A passage that does not flow logically with surrounding
                    content (missing transition, spliced ideas, internal
                    contradiction). Flag the incoherent span."""

_OUTPUT_SCHEMA = """\
[
  {
    "start": <float, seconds>,
    "end": <float, seconds>,
    "reason": "<REPEATED_TAKE | ABANDONED | MISSPOKEN | INCOHERENT>",
    "flagged_text": "<verbatim transcript text being flagged>",
    "explanation": "<one sentence explaining the issue>",
    "confidence": "<high | medium | low>"
  }
]"""


def build_chunk_prompt(chunk: Chunk, total_chunks: int) -> str:
    """Build the LLM analysis prompt for a single chunk.

    Parameters
    ----------
    chunk:
        The Chunk to analyse.
    total_chunks:
        Total number of chunks in this transcript (used in the header so the
        model knows its position in the full document).

    Returns
    -------
    str
        The complete prompt string, ready to send verbatim to an LLM.
    """
    lines: list[str] = []

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    lines.append(
        f"You are analysing chunk {chunk.chunk_id + 1} of {total_chunks} from a "
        f"spoken-word transcript. Your task is to identify semantic editing issues "
        f"that automated tools (Pass 1) cannot detect.\n"
    )
    lines.append(
        f"This chunk covers {format_timecode(chunk.start_time)} – "
        f"{format_timecode(chunk.end_time)} of the recording.\n"
    )

    # ------------------------------------------------------------------
    # Context segments (overlap from previous chunk)
    # ------------------------------------------------------------------
    if chunk.overlap_before:
        lines.append("--- CONTEXT BEFORE [DO NOT ANALYSE — for reference only] ---")
        for seg in chunk.overlap_before:
            tc = f"[{format_timecode(seg.start)} - {format_timecode(seg.end)}]"
            lines.append(f"{tc} {seg.text.strip()}")
        lines.append("")

    # ------------------------------------------------------------------
    # Core segments to analyse
    # ------------------------------------------------------------------
    lines.append("--- TRANSCRIPT TO ANALYSE ---")
    for seg in chunk.segments:
        tc = f"[{format_timecode(seg.start)} - {format_timecode(seg.end)}]"
        lines.append(f"{tc} {seg.text.strip()}")
    lines.append("")

    # ------------------------------------------------------------------
    # Context segments (overlap from next chunk)
    # ------------------------------------------------------------------
    if chunk.overlap_after:
        lines.append("--- CONTEXT AFTER [DO NOT ANALYSE — for reference only] ---")
        for seg in chunk.overlap_after:
            tc = f"[{format_timecode(seg.start)} - {format_timecode(seg.end)}]"
            lines.append(f"{tc} {seg.text.strip()}")
        lines.append("")

    # ------------------------------------------------------------------
    # Pass 1 findings (so the LLM does not duplicate mechanical catches)
    # ------------------------------------------------------------------
    if chunk.pass1_cuts_in_range:
        lines.append("--- PASS 1 FINDINGS (already flagged — skip these) ---")
        for cut in chunk.pass1_cuts_in_range:
            tc = f"[{format_timecode(cut.start)} - {format_timecode(cut.end)}]"
            lines.append(f"{tc} {cut.reason}: {cut.flagged_text!r}")
        lines.append("")

    # ------------------------------------------------------------------
    # Instructions
    # ------------------------------------------------------------------
    lines.append("--- INSTRUCTIONS ---")
    lines.append(
        "Analyse ONLY the segments in the 'TRANSCRIPT TO ANALYSE' section. "
        "Do not flag anything already listed in Pass 1 findings. "
        "Do not flag normal disfluencies (um, uh, brief pauses) — those are "
        "handled by Pass 1.\n"
    )
    lines.append("Look for the following issue types:\n")
    lines.append(_REASON_DESCRIPTIONS)
    lines.append("")
    lines.append(
        "Use the context sections (before/after) to understand flow, but "
        "only report issues within the analysed range "
        f"({format_timecode(chunk.start_time)} – {format_timecode(chunk.end_time)}).\n"
    )
    lines.append(
        "Timestamps in your response MUST fall within the analysed range. "
        "Use the exact start/end times from the transcript lines above.\n"
    )

    # ------------------------------------------------------------------
    # Output format
    # ------------------------------------------------------------------
    lines.append("--- REQUIRED OUTPUT FORMAT ---")
    lines.append(
        "Respond with ONLY a JSON array matching this schema (no prose, no markdown "
        "outside the code block):\n"
    )
    lines.append("```json")
    lines.append(_OUTPUT_SCHEMA)
    lines.append("```\n")
    lines.append("If no issues are found in this chunk, respond with exactly: []")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

# Mapping from LLM reason strings to CutReason enum values.
_REASON_MAP: dict[str, CutReason] = {
    "repeated_take": CutReason.RETAKE,
    "repeated": CutReason.RETAKE,
    "retake": CutReason.RETAKE,
    "abandoned": CutReason.FALSE_START,
    "abandoned_sentence": CutReason.FALSE_START,
    "false_start": CutReason.FALSE_START,
    "misspoken": CutReason.MISSPOKEN,
    "misspoken_word": CutReason.MISSPOKEN,
    "incoherent": CutReason.SEMANTIC,
    "incoherent_passage": CutReason.SEMANTIC,
    "semantic": CutReason.SEMANTIC,
}

_CONFIDENCE_MAP: dict[str, Confidence] = {
    "high": Confidence.HIGH,
    "medium": Confidence.MEDIUM,
    "med": Confidence.MEDIUM,
    "low": Confidence.LOW,
}

# Tolerance in seconds when validating that returned timestamps fall inside
# the chunk's time range.  A small buffer handles floating-point edge cases
# and models that round to the nearest half-second.
_TIMESTAMP_TOLERANCE = 0.5


def _extract_json(text: str) -> Optional[str]:
    """Pull raw JSON out of an LLM response.

    Handles:
    - Plain JSON (no wrapping)
    - Markdown code blocks: ```json ... ``` or ``` ... ```
    - Leading/trailing whitespace

    Returns the JSON string, or None if nothing plausible was found.
    """
    stripped = text.strip()

    # Fast path: empty / trivial responses.
    if not stripped or stripped == "[]":
        return stripped

    # Try to find a fenced code block first.
    fence_pattern = re.compile(
        r"```(?:json)?\s*\n?(.*?)\n?\s*```",
        re.DOTALL | re.IGNORECASE,
    )
    match = fence_pattern.search(stripped)
    if match:
        return match.group(1).strip()

    # If it looks like raw JSON (starts with [ or {), use it directly.
    if stripped.startswith("[") or stripped.startswith("{"):
        return stripped

    return None


def parse_chunk_response(response_text: str, chunk: Chunk) -> list[Cut]:
    """Parse an LLM response string into a list of Cut objects.

    Parameters
    ----------
    response_text:
        Raw text returned by the LLM for this chunk's prompt.
    chunk:
        The Chunk that was analysed.  Used to validate timestamps and to
        collect segment IDs for the resulting Cuts.

    Returns
    -------
    list[Cut]
        Validated Cut objects with source="pass2".  Malformed or out-of-range
        entries are logged and skipped without raising.
    """
    json_str = _extract_json(response_text)

    if not json_str or json_str.strip() == "[]":
        return []

    try:
        raw_entries = json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.warning(
            "Chunk %d: failed to parse JSON response: %s\nRaw text: %.300s",
            chunk.chunk_id,
            exc,
            response_text,
        )
        return []

    if not isinstance(raw_entries, list):
        logger.warning(
            "Chunk %d: expected a JSON array, got %s",
            chunk.chunk_id,
            type(raw_entries).__name__,
        )
        return []

    cuts: list[Cut] = []
    range_lo = chunk.start_time - _TIMESTAMP_TOLERANCE
    range_hi = chunk.end_time + _TIMESTAMP_TOLERANCE

    for idx, entry in enumerate(raw_entries):
        if not isinstance(entry, dict):
            logger.warning("Chunk %d entry %d: not a dict, skipping", chunk.chunk_id, idx)
            continue

        # --- Required numeric fields ---
        try:
            start = float(entry["start"])
            end = float(entry["end"])
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "Chunk %d entry %d: missing or invalid start/end (%s), skipping",
                chunk.chunk_id, idx, exc,
            )
            continue

        if end <= start:
            logger.warning(
                "Chunk %d entry %d: end (%.2f) <= start (%.2f), skipping",
                chunk.chunk_id, idx, end, start,
            )
            continue

        # --- Timestamp range validation ---
        if start < range_lo or end > range_hi:
            logger.warning(
                "Chunk %d entry %d: timestamps [%.2f, %.2f] outside chunk range "
                "[%.2f, %.2f] (±%.1f s tolerance), skipping",
                chunk.chunk_id, idx, start, end,
                chunk.start_time, chunk.end_time, _TIMESTAMP_TOLERANCE,
            )
            continue

        # --- Reason ---
        raw_reason = str(entry.get("reason", "")).lower().strip()
        reason = _REASON_MAP.get(raw_reason, CutReason.SEMANTIC)
        if raw_reason not in _REASON_MAP:
            logger.warning(
                "Chunk %d entry %d: unknown reason %r, defaulting to SEMANTIC",
                chunk.chunk_id, idx, entry.get("reason"),
            )

        # --- Confidence ---
        raw_conf = str(entry.get("confidence", "")).lower().strip()
        confidence = _CONFIDENCE_MAP.get(raw_conf, Confidence.MEDIUM)

        # --- Text fields ---
        flagged_text = str(entry.get("flagged_text", "")).strip()
        explanation = str(entry.get("explanation", "")).strip()

        # --- Segment IDs that overlap this cut ---
        segment_ids = [
            seg.id
            for seg in chunk.segments
            if seg.start < end and seg.end > start
        ]

        cuts.append(Cut(
            start=start,
            end=end,
            reason=reason.value,
            confidence=confidence.value,
            flagged_text=flagged_text,
            explanation=explanation,
            source="pass2",
            segment_ids=segment_ids,
        ))

    return cuts
