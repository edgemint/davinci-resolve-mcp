"""Pass 1: Mechanical analysis of a CrisperWhisper transcript for cut detection.

Detects everything that can be found programmatically without semantic understanding:
fillers, hallucinations, timestamp artifacts, stammers, false starts, and retakes.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from output import Transcript, Segment, Word

from .models import Cut, CutReason, Confidence, AnalysisConfig


# ---------------------------------------------------------------------------
# Internal types
# ---------------------------------------------------------------------------

class WordWithIndex(NamedTuple):
    word: Word
    index: int
    segment_id: int


# ---------------------------------------------------------------------------
# Filler word patterns
# ---------------------------------------------------------------------------

# Standalone fillers that CrisperWhisper may not tag explicitly.
# Excludes "like", "you know", "basically", "so", "right" — too many false positives.
_FILLER_RE = re.compile(
    r"^(?:um+|uh+|hmm*|ah+|er+)$",
    re.IGNORECASE,
)

# Punctuation to strip when normalising a word for filler / stammer matching.
_TRAILING_PUNCT_RE = re.compile(r"[^\w']+$")
_LEADING_PUNCT_RE = re.compile(r"^[^\w']+")


def _strip_punct(text: str) -> str:
    """Strip leading and trailing punctuation from *text*."""
    return _LEADING_PUNCT_RE.sub("", _TRAILING_PUNCT_RE.sub("", text))


def _normalise(text: str) -> str:
    """Lowercase and strip punctuation for comparison."""
    return _strip_punct(text).lower()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flatten_words(transcript: Transcript) -> list[WordWithIndex]:
    """Return all words across all segments as a flat indexed list."""
    result: list[WordWithIndex] = []
    idx = 0
    for seg in transcript.segments:
        for w in seg.words:
            result.append(WordWithIndex(word=w, index=idx, segment_id=seg.id))
            idx += 1
    return result


def _get_context(words: list[WordWithIndex], index: int, n: int = 5) -> tuple[str, str]:
    """Return (context_before, context_after) using the n nearest words."""
    before_tokens: list[str] = []
    for wi in words[max(0, index - n) : index]:
        before_tokens.append(wi.word.word)
    after_tokens: list[str] = []
    for wi in words[index + 1 : index + 1 + n]:
        after_tokens.append(wi.word.word)
    return " ".join(before_tokens), " ".join(after_tokens)


def _confidence_rank(c: str) -> int:
    """Numeric rank so we can keep the higher one when merging."""
    return {Confidence.HIGH: 3, Confidence.MEDIUM: 2, Confidence.LOW: 1}.get(c, 0)


# ---------------------------------------------------------------------------
# Detector 1 — Fillers
# ---------------------------------------------------------------------------

def _detect_fillers(words: list[WordWithIndex], config: AnalysisConfig) -> list[Cut]:
    cuts: list[Cut] = []
    for wi in words:
        w = wi.word
        is_filler = (
            getattr(w, "type", None) == "filler"
            or _FILLER_RE.match(_strip_punct(w.word))
        )
        if not is_filler:
            continue
        ctx_before, ctx_after = _get_context(words, wi.index)
        cuts.append(Cut(
            start=w.start,
            end=w.end,
            reason=CutReason.FILLER,
            confidence=Confidence.HIGH,
            flagged_text=w.word,
            context_before=ctx_before,
            context_after=ctx_after,
            explanation=f"Filler word detected: {w.word!r}",
            segment_ids=[wi.segment_id],
        ))
    return cuts


# ---------------------------------------------------------------------------
# Detector 2 — Hallucinations
# ---------------------------------------------------------------------------

def _detect_hallucinations(transcript: Transcript, config: AnalysisConfig) -> list[Cut]:
    """Flag segments whose words-per-second is impossibly high, or whose
    timestamps are reversed.  Adjacent flagged segments are merged."""
    flagged: list[Segment] = []

    for seg in transcript.segments:
        duration = seg.end - seg.start
        if duration <= 0:
            flagged.append(seg)
            continue
        word_count = len(seg.words) if seg.words else len(seg.text.split())
        wps = word_count / duration
        if wps > config.hallucination_wps_threshold:
            flagged.append(seg)

    if not flagged:
        return []

    # Merge adjacent (consecutive in the original list) flagged segments.
    seg_index = {seg.id: i for i, seg in enumerate(transcript.segments)}
    cuts: list[Cut] = []
    group: list[Segment] = [flagged[0]]

    def _flush(group: list[Segment]) -> Cut:
        seg_ids = [s.id for s in group]
        text = " ".join(s.text for s in group)
        duration = group[-1].end - group[0].start
        wps_info = (
            f"{len(text.split()) / duration:.1f} wps"
            if duration > 0
            else "reversed timestamps"
        )
        return Cut(
            start=group[0].start,
            end=group[-1].end,
            reason=CutReason.HALLUCINATION,
            confidence=Confidence.HIGH,
            flagged_text=text,
            explanation=f"Likely hallucination: {wps_info}",
            segment_ids=seg_ids,
        )

    for seg in flagged[1:]:
        prev_id = group[-1].id
        cur_id = seg.id
        # Adjacent if they are consecutive in the original segment list.
        if seg_index.get(cur_id, -999) == seg_index.get(prev_id, -998) + 1:
            group.append(seg)
        else:
            cuts.append(_flush(group))
            group = [seg]

    cuts.append(_flush(group))
    return cuts


# ---------------------------------------------------------------------------
# Detector 3 — Timestamp artifacts
# ---------------------------------------------------------------------------

def _detect_timestamp_artifacts(words: list[WordWithIndex], config: AnalysisConfig) -> list[Cut]:
    """Single words with suspiciously long duration are timestamp padding errors."""
    cuts: list[Cut] = []
    for wi in words:
        w = wi.word
        duration = w.end - w.start
        if duration > config.artifact_word_duration:
            ctx_before, ctx_after = _get_context(words, wi.index)
            cuts.append(Cut(
                start=w.start,
                end=w.end,
                reason=CutReason.ARTIFACT,
                confidence=Confidence.MEDIUM,
                flagged_text=w.word,
                context_before=ctx_before,
                context_after=ctx_after,
                explanation=(
                    f"Word {w.word!r} spans {duration:.2f}s "
                    f"(threshold {config.artifact_word_duration}s) — possible dead air"
                ),
                segment_ids=[wi.segment_id],
            ))
    return cuts


# ---------------------------------------------------------------------------
# Detector 4 — Stammers
# ---------------------------------------------------------------------------

def _detect_stammers(words: list[WordWithIndex], config: AnalysisConfig) -> list[Cut]:
    """Detect immediate word repetitions (stammer/stutter).

    Cuts the FIRST occurrence; keeps the clean second word.
    Skips pairs that look intentional (both have trailing commas, or gap < 0.15s).
    """
    cuts: list[Cut] = []
    i = 0
    while i < len(words) - 1:
        wi_a = words[i]
        wi_b = words[i + 1]
        wa, wb = wi_a.word, wi_b.word

        norm_a = _normalise(wa.word)
        norm_b = _normalise(wb.word)

        if norm_a and norm_b and norm_a == norm_b:
            # Check intentional: both words end with a comma (deliberate rhythm).
            both_comma = wa.word.rstrip().endswith(",") and wb.word.rstrip().endswith(",")
            gap = wb.start - wa.end
            # A very tight gap (< 0.15s) without punctuation is typically a stammer;
            # but if BOTH have commas it's stylistic — skip.
            if not both_comma:
                ctx_before, ctx_after = _get_context(words, wi_a.index)
                cuts.append(Cut(
                    start=wa.start,
                    end=wa.end,
                    reason=CutReason.STAMMER,
                    confidence=Confidence.MEDIUM,
                    flagged_text=wa.word,
                    context_before=ctx_before,
                    context_after=ctx_after,
                    explanation=(
                        f"Stammer: {wa.word!r} repeated immediately "
                        f"(gap {gap:.2f}s)"
                    ),
                    segment_ids=list({wi_a.segment_id, wi_b.segment_id}),
                ))
                # Skip the pair so we don't double-flag.
                i += 2
                continue
        i += 1
    return cuts


# ---------------------------------------------------------------------------
# Detector 5 — False starts
# ---------------------------------------------------------------------------

def _detect_false_starts(words: list[WordWithIndex], config: AnalysisConfig) -> list[Cut]:
    """Detect short phrases that trail off into a long pause (abandoned thought).

    Pattern: [sentence boundary / long pause before] → [1-N words] → [gap >= min_gap]
    """
    cuts: list[Cut] = []
    max_words = config.false_start_max_words
    min_gap = config.false_start_min_gap
    sentence_boundary_gap = 0.5  # gap that marks a new sentence / clause boundary

    i = 0
    while i < len(words):
        wi = words[i]

        # Determine whether there is a sentence boundary immediately before words[i].
        if i == 0:
            gap_before = sentence_boundary_gap  # treat start of file as a boundary
        else:
            gap_before = wi.word.start - words[i - 1].word.end

        if gap_before < sentence_boundary_gap:
            i += 1
            continue

        # We are at a potential sentence boundary.  Look ahead for 1..max_words words.
        for phrase_len in range(1, max_words + 1):
            end_idx = i + phrase_len
            if end_idx >= len(words):
                break

            last_wi = words[end_idx - 1]

            # Gap after the phrase.
            if end_idx < len(words):
                gap_after = words[end_idx].word.start - last_wi.word.end
            else:
                # Phrase runs to the end of the file — not a false start.
                break

            if gap_after >= min_gap:
                phrase_words = words[i:end_idx]
                phrase_text = " ".join(pw.word.word for pw in phrase_words)
                ctx_before, _ = _get_context(words, i)
                _, ctx_after = _get_context(words, end_idx - 1)
                seg_ids = list({pw.segment_id for pw in phrase_words})
                cuts.append(Cut(
                    start=words[i].word.start,
                    end=last_wi.word.end,
                    reason=CutReason.FALSE_START,
                    confidence=Confidence.MEDIUM,
                    flagged_text=phrase_text,
                    context_before=ctx_before,
                    context_after=ctx_after,
                    explanation=(
                        f"False start: {phrase_len}-word phrase "
                        f"followed by {gap_after:.2f}s pause"
                    ),
                    segment_ids=seg_ids,
                ))
                # Advance past this phrase.
                i = end_idx
                break
        else:
            i += 1

    return cuts


# ---------------------------------------------------------------------------
# Detector 6 — Retakes
# ---------------------------------------------------------------------------

_RETAKE_WINDOW = 15.0  # seconds to look ahead for a matching N-gram
_NGRAM_MIN = 3
_NGRAM_MAX = 8


def _make_ngrams(words: list[WordWithIndex], start: int, n: int) -> list[str]:
    """Return the n normalised word strings starting at *start*, or [] if OOB."""
    end = start + n
    if end > len(words):
        return []
    return [_normalise(words[j].word.word) for j in range(start, end)]


def _detect_retakes(words: list[WordWithIndex], config: AnalysisConfig) -> list[Cut]:
    """Find repeated N-grams within a sliding window; flag the first occurrence."""
    cuts: list[Cut] = []

    # To avoid flagging the same first-occurrence start twice, track what we've cut.
    cut_starts: set[int] = set()

    for i in range(len(words)):
        if i in cut_starts:
            continue

        wi_first = words[i]
        window_end_time = wi_first.word.start + _RETAKE_WINDOW

        for n in range(_NGRAM_MAX, _NGRAM_MIN - 1, -1):
            ngram_a = _make_ngrams(words, i, n)
            if not ngram_a or any(t == "" for t in ngram_a):
                continue

            # Search ahead within the time window.
            for j in range(i + 1, len(words)):
                if words[j].word.start > window_end_time:
                    break

                ngram_b = _make_ngrams(words, j, n)
                if ngram_b != ngram_a:
                    continue

                # Found a retake: [i .. i+n-1] is the false take, [j .. j+n-1] is the keep.
                first_end_idx = i + n - 1
                first_wi_last = words[first_end_idx]

                # Extend the cut to cover any trailing words between the two N-grams.
                cut_end = first_wi_last.word.end

                phrase_text = " ".join(words[k].word.word for k in range(i, i + n))
                repeat_text = " ".join(words[k].word.word for k in range(j, j + n))

                ctx_before, _ = _get_context(words, i)
                _, ctx_after = _get_context(words, j + n - 1)

                seg_ids = list({words[k].segment_id for k in range(i, i + n)})
                confidence = Confidence.HIGH  # exact normalised match

                cuts.append(Cut(
                    start=wi_first.word.start,
                    end=cut_end,
                    reason=CutReason.RETAKE,
                    confidence=confidence,
                    flagged_text=phrase_text,
                    context_before=ctx_before,
                    context_after=ctx_after,
                    explanation=(
                        f"Retake: {n}-gram {phrase_text!r} repeated as "
                        f"{repeat_text!r} at t={words[j].word.start:.2f}s"
                    ),
                    segment_ids=seg_ids,
                ))
                cut_starts.add(i)
                # Prefer the longest matching N-gram — stop searching other sizes.
                break
            else:
                # Inner loop exhausted without a break — try a smaller n.
                continue
            # Inner loop broke (match found) — also break the n-loop.
            break

    return cuts


# ---------------------------------------------------------------------------
# Deduplication / merge
# ---------------------------------------------------------------------------

def _sort_and_deduplicate(cuts: list[Cut]) -> list[Cut]:
    """Sort cuts by start time and merge overlapping ones.

    Two cuts are merged if their overlap exceeds 50% of the shorter cut's duration.
    When merging, the higher-confidence reason is retained.
    """
    if not cuts:
        return []

    cuts = sorted(cuts, key=lambda c: c.start)

    merged: list[Cut] = [cuts[0]]
    for cur in cuts[1:]:
        prev = merged[-1]

        overlap_start = max(prev.start, cur.start)
        overlap_end = min(prev.end, cur.end)
        overlap = max(0.0, overlap_end - overlap_start)

        shorter_duration = min(prev.end - prev.start, cur.end - cur.start)
        if shorter_duration <= 0 or overlap / shorter_duration > 0.5:
            # Merge: extend the window and keep the higher-confidence entry.
            if _confidence_rank(cur.confidence) > _confidence_rank(prev.confidence):
                # Use the current cut's metadata but span both time ranges.
                new_cut = Cut(
                    start=min(prev.start, cur.start),
                    end=max(prev.end, cur.end),
                    reason=cur.reason,
                    confidence=cur.confidence,
                    flagged_text=cur.flagged_text,
                    context_before=prev.context_before,
                    context_after=cur.context_after,
                    explanation=f"[merged] {prev.explanation} | {cur.explanation}",
                    segment_ids=list(set(prev.segment_ids + cur.segment_ids)),
                )
            else:
                new_cut = Cut(
                    start=min(prev.start, cur.start),
                    end=max(prev.end, cur.end),
                    reason=prev.reason,
                    confidence=prev.confidence,
                    flagged_text=prev.flagged_text,
                    context_before=prev.context_before,
                    context_after=cur.context_after,
                    explanation=f"[merged] {prev.explanation} | {cur.explanation}",
                    segment_ids=list(set(prev.segment_ids + cur.segment_ids)),
                )
            merged[-1] = new_cut
        else:
            merged.append(cur)

    return merged


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_pass1(transcript: Transcript, config: AnalysisConfig | None = None) -> list[Cut]:
    """Run all mechanical detectors and return a deduplicated, sorted cut list.

    Args:
        transcript: A :class:`Transcript` produced by any backend.
        config: Optional :class:`AnalysisConfig`; defaults are used if omitted.

    Returns:
        Sorted, deduplicated list of :class:`Cut` objects.
    """
    if config is None:
        config = AnalysisConfig()

    words = _flatten_words(transcript)

    all_cuts: list[Cut] = []
    all_cuts.extend(_detect_fillers(words, config))
    all_cuts.extend(_detect_hallucinations(transcript, config))
    all_cuts.extend(_detect_timestamp_artifacts(words, config))
    all_cuts.extend(_detect_stammers(words, config))
    all_cuts.extend(_detect_false_starts(words, config))
    all_cuts.extend(_detect_retakes(words, config))

    return _sort_and_deduplicate(all_cuts)
