#!/usr/bin/env python3
"""Timed audio transcription tool.

Usage:
    python tools/transcribe/transcribe.py recording.wav                    # OpenAI API
    python tools/transcribe/transcribe.py recording.wav --local            # CrisperWhisper
    python tools/transcribe/transcribe.py recording.wav --local -o out.json
"""

import argparse
import sys
from pathlib import Path

# Support both direct execution and module execution
if __name__ == "__main__" and __package__ is None:
    _root = str(Path(__file__).resolve().parent.parent.parent)
    if _root not in sys.path:
        sys.path.insert(0, _root)


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe audio with word-level timestamps."
    )
    parser.add_argument("audio", help="Path to audio file (mp3, wav, flac, etc.)")
    parser.add_argument(
        "--local",
        action="store_true",
        help="Use CrisperWhisper locally instead of OpenAI API",
    )
    parser.add_argument(
        "--language", "-l",
        default="en",
        help="Language code (default: en)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output JSON path (default: <input_name>.transcript.json)",
    )

    args = parser.parse_args()

    audio_path = Path(args.audio).resolve()
    if not audio_path.exists():
        print(f"Error: file not found: {audio_path}", file=sys.stderr)
        sys.exit(1)

    if audio_path.stat().st_size == 0:
        print("Error: audio file is empty", file=sys.stderr)
        sys.exit(1)

    # Default output path: input_name.transcript.json
    if args.output is None:
        output_path = audio_path.parent / (audio_path.stem + ".transcript.json")
    else:
        output_path = Path(args.output).resolve()
        if not output_path.parent.exists():
            print(f"Error: output directory does not exist: {output_path.parent}", file=sys.stderr)
            sys.exit(1)

    # Select backend
    if args.local:
        print("Transcribing with CrisperWhisper (local)...")
        from tools.transcribe.backends.crisper_backend import transcribe
    else:
        print("Transcribing with OpenAI Whisper API...")
        from tools.transcribe.backends.openai_backend import transcribe

    transcript = transcribe(str(audio_path), language=args.language)
    transcript.save(str(output_path))
    print(f"Transcript saved to: {output_path}")

    # Print summary
    n_words = sum(len(s.words) for s in transcript.segments)
    n_fillers = sum(1 for s in transcript.segments for w in s.words if w.type == "filler")
    print(f"  Segments: {len(transcript.segments)}")
    print(f"  Words: {n_words}")
    if n_fillers:
        print(f"  Fillers detected: {n_fillers}")
    print(f"  Duration: {transcript.metadata.duration_seconds:.1f}s")


if __name__ == "__main__":
    main()
