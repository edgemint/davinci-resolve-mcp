#!/usr/bin/env python3
"""Transcript analysis — generates cut lists from transcription JSON.

Usage:
    python tools/transcribe/analyze.py AudioFiles/GRRM.transcript.json
    python tools/transcribe/analyze.py AudioFiles/GRRM.transcript.json --pass1-only
    python tools/transcribe/analyze.py AudioFiles/GRRM.transcript.json -o cuts.json
"""

import argparse
import json
import sys
from pathlib import Path

# Support both direct execution and module execution
if __name__ == "__main__" and __package__ is None:
    _root = str(Path(__file__).resolve().parent.parent.parent)
    if _root not in sys.path:
        sys.path.insert(0, _root)

from tools.transcribe.output import Transcript, TranscriptMetadata, Segment, Word
from tools.transcribe.analyzers.models import AnalysisConfig, CutList
from tools.transcribe.analyzers.pass1 import run_pass1
from tools.transcribe.analyzers.pass2 import chunk_transcript, build_chunk_prompt
from tools.transcribe.analyzers.merger import build_cut_list
from tools.transcribe.analyzers.report import generate_report


def load_transcript(path: str) -> Transcript:
    """Load a transcript JSON file into dataclass objects."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    meta = data["metadata"]
    metadata = TranscriptMetadata(
        file=meta["file"],
        duration_seconds=meta["duration_seconds"],
        backend=meta["backend"],
        language=meta["language"],
        timestamp=meta.get("timestamp", ""),
    )

    segments = []
    for seg in data["segments"]:
        words = []
        for w in seg.get("words", []):
            words.append(Word(
                word=w["word"],
                start=w["start"],
                end=w["end"],
                type=w.get("type"),
            ))
        segments.append(Segment(
            id=seg["id"],
            start=seg["start"],
            end=seg["end"],
            text=seg["text"],
            words=words,
        ))

    return Transcript(metadata=metadata, segments=segments)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze transcript and generate cut list."
    )
    parser.add_argument("transcript", help="Path to .transcript.json file")
    parser.add_argument(
        "--output", "-o",
        help="Output path for JSON cut list (default: <input>.cutlist.json)",
    )
    parser.add_argument(
        "--report", "-r",
        help="Markdown report path (default: <input>.cutlist.md)",
    )
    parser.add_argument(
        "--pass1-only",
        action="store_true",
        help="Run only Pass 1 (mechanical analysis), skip LLM semantic pass",
    )
    parser.add_argument(
        "--pause-threshold",
        type=float,
        default=1.5,
        help="Pause threshold for retake detection in seconds (default: 1.5)",
    )
    parser.add_argument(
        "--chunk-duration",
        type=float,
        default=150.0,
        help="Chunk duration for Pass 2 in seconds (default: 150)",
    )
    parser.add_argument(
        "--dump-chunks",
        action="store_true",
        help="Print Pass 2 chunk prompts to stdout (for manual LLM dispatch)",
    )

    args = parser.parse_args()

    transcript_path = Path(args.transcript).resolve()
    if not transcript_path.exists():
        print(f"Error: file not found: {transcript_path}", file=sys.stderr)
        sys.exit(1)

    stem = transcript_path.stem.replace(".transcript", "")
    output_dir = transcript_path.parent

    output_path = Path(args.output).resolve() if args.output else output_dir / f"{stem}.cutlist.json"
    report_path = Path(args.report).resolve() if args.report else output_dir / f"{stem}.cutlist.md"

    config = AnalysisConfig(
        pause_retake_threshold=args.pause_threshold,
        chunk_duration=args.chunk_duration,
    )

    print(f"Loading transcript: {transcript_path}")
    transcript = load_transcript(str(transcript_path))
    n_words = sum(len(s.words) for s in transcript.segments)
    print(f"  {len(transcript.segments)} segments, {n_words} words, "
          f"{transcript.metadata.duration_seconds:.1f}s")

    # --- Pass 1 ---
    print("\n--- Pass 1: Mechanical analysis ---")
    pass1_cuts = run_pass1(transcript, config)
    pass1_stats = {
        "segments_analyzed": len(transcript.segments),
        "words_analyzed": n_words,
        "cuts_found": len(pass1_cuts),
    }
    print(f"  Pass 1 found {len(pass1_cuts)} cuts")
    for cut in pass1_cuts:
        print(f"    [{cut.start:.2f}-{cut.end:.2f}] {cut.reason}: {cut.flagged_text[:60]}")

    # --- Pass 2 chunks ---
    pass2_cuts = []
    pass2_stats = {"chunks": 0, "cuts_found": 0}

    if not args.pass1_only:
        print("\n--- Pass 2: Preparing semantic analysis chunks ---")
        chunks = chunk_transcript(transcript, config, pass1_cuts)
        pass2_stats["chunks"] = len(chunks)
        print(f"  Created {len(chunks)} chunks")

        if args.dump_chunks:
            for chunk in chunks:
                prompt = build_chunk_prompt(chunk, len(chunks))
                print(f"\n{'='*60}")
                print(f"CHUNK {chunk.chunk_id} [{chunk.start_time:.1f}s - {chunk.end_time:.1f}s]")
                print(f"{'='*60}")
                print(prompt)
        else:
            print("  (Pass 2 requires LLM dispatch — use --dump-chunks for manual prompts)")
            print("  (Agent orchestration will handle dispatch automatically)")

    # --- Build output ---
    cut_list = build_cut_list(
        source_file=transcript.metadata.file,
        duration=transcript.metadata.duration_seconds,
        config=config,
        pass1_cuts=pass1_cuts,
        pass2_cuts=pass2_cuts,
        pass1_stats=pass1_stats,
        pass2_stats=pass2_stats,
    )

    cut_list.save_json(str(output_path))
    print(f"\nCut list saved to: {output_path}")

    report_text = generate_report(cut_list)
    with open(str(report_path), "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"Report saved to: {report_path}")

    print(f"\nDone. {len(cut_list.cuts)} total cuts, "
          f"{sum(c.end - c.start for c in cut_list.cuts):.1f}s of content to review.")


if __name__ == "__main__":
    main()
