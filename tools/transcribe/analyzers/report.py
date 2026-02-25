"""Generate Markdown report from a CutList."""

from .models import CutList, Cut, Confidence


def format_timecode(seconds: float) -> str:
    """Format seconds as MM:SS.ss (e.g., 02:34.56)."""
    total_seconds = max(0.0, seconds)
    minutes = int(total_seconds // 60)
    secs = total_seconds - minutes * 60
    return f"{minutes:02d}:{secs:05.2f}"


def _truncate(text: str, max_len: int = 60) -> str:
    """Truncate text to max_len characters, appending ellipsis if cut."""
    text = text.replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _count_by(cuts: list, attr: str) -> dict:
    """Count cuts grouped by the value of the given attribute."""
    counts: dict = {}
    for cut in cuts:
        val = getattr(cut, attr, "unknown")
        counts[val] = counts.get(val, 0) + 1
    return counts


def generate_report(cut_list: CutList) -> str:
    """Generate a Markdown report from a CutList.

    Structure
    ---------
    # Transcript Analysis Report

    ## Summary
    - Source file, duration
    - Total cuts found, total cut time, percentage of recording
    - Breakdown by reason (filler=N, retake=N, etc.)
    - Breakdown by confidence (high=N, medium=N, low=N)
    - Breakdown by source (pass1=N, pass2=N)

    ## Cut List
    A markdown table with columns:
    | # | Time | Duration | Reason | Conf. | Text | Explanation |

    ## Notes
    - LOW confidence cuts require manual review
    - Timestamp artifact cuts may need boundary adjustment
    - HALLUCINATION cuts indicate transcription errors, not speech issues
    """
    cuts = cut_list.cuts
    duration = cut_list.duration_seconds

    total_cut_time = sum(max(0.0, c.end - c.start) for c in cuts)
    pct = (total_cut_time / duration * 100) if duration > 0 else 0.0

    by_reason = _count_by(cuts, "reason")
    by_confidence = _count_by(cuts, "confidence")
    by_source = _count_by(cuts, "source")

    lines: list[str] = []

    # ------------------------------------------------------------------ Header
    lines.append("# Transcript Analysis Report")
    lines.append("")

    # ----------------------------------------------------------------- Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Source file:** `{cut_list.source_file}`")
    lines.append(f"- **Duration:** {format_timecode(duration)} ({duration:.1f} s)")
    lines.append(f"- **Total cuts found:** {len(cuts)}")
    lines.append(
        f"- **Total cut time:** {total_cut_time:.1f} s"
        f" ({pct:.1f}% of recording)"
    )
    lines.append("")

    # Breakdown by reason
    if by_reason:
        reason_parts = ", ".join(
            f"{reason}={count}"
            for reason, count in sorted(by_reason.items())
        )
        lines.append(f"- **By reason:** {reason_parts}")

    # Breakdown by confidence
    conf_order = [Confidence.HIGH, Confidence.MEDIUM, Confidence.LOW]
    conf_parts = []
    for conf in conf_order:
        n = by_confidence.get(conf, by_confidence.get(conf.value, 0))
        conf_parts.append(f"{conf.value}={n}")
    lines.append(f"- **By confidence:** {', '.join(conf_parts)}")

    # Breakdown by source
    if by_source:
        source_parts = ", ".join(
            f"{src}={count}"
            for src, count in sorted(by_source.items())
        )
        lines.append(f"- **By source:** {source_parts}")

    lines.append("")

    # ---------------------------------------------------------------- Cut list
    lines.append("## Cut List")
    lines.append("")

    if not cuts:
        lines.append("_No cuts found._")
    else:
        header = "| # | Time | Duration | Reason | Conf. | Text | Explanation |"
        separator = "|---|------|----------|--------|-------|------|-------------|"
        lines.append(header)
        lines.append(separator)

        for idx, cut in enumerate(cuts, start=1):
            time_str = (
                f"{format_timecode(cut.start)} - {format_timecode(cut.end)}"
            )
            dur_str = f"{max(0.0, cut.end - cut.start):.1f} s"
            text_cell = _truncate(cut.flagged_text, 60)
            explanation_cell = _truncate(cut.explanation, 80)

            # Escape pipe characters inside cells so the table renders correctly
            def esc(s: str) -> str:
                return s.replace("|", "\\|")

            row = (
                f"| {idx}"
                f" | {esc(time_str)}"
                f" | {esc(dur_str)}"
                f" | {esc(cut.reason)}"
                f" | {esc(cut.confidence)}"
                f" | {esc(text_cell)}"
                f" | {esc(explanation_cell)}"
                f" |"
            )
            lines.append(row)

    lines.append("")

    # ------------------------------------------------------------------- Notes
    lines.append("## Notes")
    lines.append("")
    lines.append(
        "- **LOW confidence** cuts require manual review before applying to the timeline."
    )
    lines.append(
        "- **`timestamp_artifact`** cuts may have imprecise boundaries; "
        "adjust start/end by a few frames before cutting."
    )
    lines.append(
        "- **`hallucination`** cuts indicate likely transcription errors, "
        "not speech issues — verify the source audio before cutting."
    )
    lines.append("")

    return "\n".join(lines)
