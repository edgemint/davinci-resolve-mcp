"""Merge Pass 1 and Pass 2 cut lists."""

from .models import Cut, CutList, AnalysisConfig, Confidence

# Confidence ordering for comparison (higher index = higher confidence)
_CONFIDENCE_RANK = {
    Confidence.LOW: 0,
    Confidence.MEDIUM: 1,
    Confidence.HIGH: 2,
    # Also handle raw strings in case cuts carry string values
    "low": 0,
    "medium": 1,
    "high": 2,
}

# Pass 1 reasons are "mechanical" (pattern-matched) and preferred over semantic
_PASS1_REASONS = {
    "filler",
    "long_pause",
    "stammer",
    "false_start",
    "retake",
    "hallucination",
    "timestamp_artifact",
}

_ADJACENT_GAP = 0.3  # seconds — cuts closer than this are merged
_OVERLAP_THRESHOLD = 0.5  # fraction of shorter cut that must overlap to trigger merge


def _overlap_fraction(a: Cut, b: Cut) -> float:
    """Return overlap length / shorter-cut duration, or 0.0 if no overlap."""
    overlap_start = max(a.start, b.start)
    overlap_end = min(a.end, b.end)
    overlap = overlap_end - overlap_start
    if overlap <= 0:
        return 0.0
    shorter = min(a.end - a.start, b.end - b.start)
    if shorter <= 0:
        return 0.0
    return overlap / shorter


def _gap(a: Cut, b: Cut) -> float:
    """Return the gap between two cuts (assumes a.start <= b.start)."""
    return b.start - a.end


def _higher_confidence(c1: str, c2: str) -> str:
    """Return whichever confidence string ranks higher."""
    if _CONFIDENCE_RANK.get(c1, 0) >= _CONFIDENCE_RANK.get(c2, 0):
        return c1
    return c2


def _preferred_reason(a: Cut, b: Cut) -> str:
    """Pick the more specific/mechanical reason between two cuts.

    Pass 1 mechanical reasons are preferred over pass 2 semantic reasons.
    When both are the same pass, keep the one from the cut with higher confidence.
    """
    a_is_mechanical = a.reason in _PASS1_REASONS
    b_is_mechanical = b.reason in _PASS1_REASONS
    if a_is_mechanical and not b_is_mechanical:
        return a.reason
    if b_is_mechanical and not a_is_mechanical:
        return b.reason
    # Both mechanical or both semantic — prefer higher confidence's reason
    if _CONFIDENCE_RANK.get(a.confidence, 0) >= _CONFIDENCE_RANK.get(b.confidence, 0):
        return a.reason
    return b.reason


def _merge_pair(a: Cut, b: Cut) -> Cut:
    """Merge two overlapping or adjacent cuts into one."""
    merged_start = min(a.start, b.start)
    merged_end = max(a.end, b.end)
    confidence = _higher_confidence(a.confidence, b.confidence)
    reason = _preferred_reason(a, b)

    # Combine explanations, dropping duplicates while preserving order
    parts = []
    seen = set()
    for text in (a.explanation, b.explanation):
        for part in text.split(" | "):
            part = part.strip()
            if part and part not in seen:
                parts.append(part)
                seen.add(part)
    explanation = " | ".join(parts)

    # Prefer the flagged_text from the cut with higher confidence
    if _CONFIDENCE_RANK.get(a.confidence, 0) >= _CONFIDENCE_RANK.get(b.confidence, 0):
        flagged_text = a.flagged_text
        context_before = a.context_before
        context_after = b.context_after
    else:
        flagged_text = b.flagged_text
        context_before = a.context_before
        context_after = b.context_after

    # Source is "both" when the merge crosses passes, otherwise inherit
    source = "both" if a.source != b.source else a.source

    # Union segment IDs
    segment_ids = sorted(set(a.segment_ids) | set(b.segment_ids))

    return Cut(
        start=merged_start,
        end=merged_end,
        reason=reason,
        confidence=confidence,
        flagged_text=flagged_text,
        context_before=context_before,
        context_after=context_after,
        explanation=explanation,
        source=source,
        segment_ids=segment_ids,
    )


def _should_merge(a: Cut, b: Cut) -> bool:
    """Return True if two cuts (sorted by start) should be merged."""
    if _overlap_fraction(a, b) > _OVERLAP_THRESHOLD:
        return True
    if a.end <= b.start and _gap(a, b) < _ADJACENT_GAP:
        return True
    return False


def merge_cuts(pass1_cuts: list, pass2_cuts: list, config) -> list:
    """Merge and deduplicate cuts from both passes.

    Rules:
    1. Combine both lists and sort by start time.
    2. If two cuts overlap by >50% of the shorter cut's duration, merge them:
       - Use the earlier start, later end.
       - Keep the higher confidence (HIGH > MEDIUM > LOW).
       - Keep the more specific reason (prefer pass1 mechanical reasons).
       - Combine explanations with " | ".
    3. If two cuts are adjacent (gap < 0.3 s), merge them.
    4. Validate: no cut extends beyond transcript duration (clamp if needed).
       Clamping is applied by the caller via build_cut_list, not here.
    """
    combined = sorted(pass1_cuts + pass2_cuts, key=lambda c: (c.start, c.end))

    if not combined:
        return []

    merged: list[Cut] = [combined[0]]

    for current in combined[1:]:
        prev = merged[-1]
        if _should_merge(prev, current):
            merged[-1] = _merge_pair(prev, current)
        else:
            merged.append(current)

    return merged


def build_cut_list(
    source_file: str,
    duration: float,
    config,
    pass1_cuts: list,
    pass2_cuts: list,
    pass1_stats: dict,
    pass2_stats: dict,
) -> CutList:
    """Build the final CutList with merged results and statistics."""
    merged = merge_cuts(pass1_cuts, pass2_cuts, config)

    # Clamp every cut to [0, duration]
    clamped: list[Cut] = []
    for cut in merged:
        clamped_start = max(0.0, cut.start)
        clamped_end = min(duration, cut.end)
        if clamped_end <= clamped_start:
            # Degenerate after clamping — discard
            continue
        if clamped_start != cut.start or clamped_end != cut.end:
            import dataclasses
            cut = dataclasses.replace(cut, start=clamped_start, end=clamped_end)
        clamped.append(cut)

    return CutList(
        source_file=source_file,
        duration_seconds=duration,
        config=config,
        cuts=clamped,
        pass1_stats=pass1_stats,
        pass2_stats=pass2_stats,
    )
