# Timed Audio Transcription Tool — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a standalone CLI tool that transcribes audio files with word-level timestamps, producing structured JSON for LLM-driven edit point identification.

**Architecture:** Two-backend design — OpenAI Whisper API (fast/easy) and full CrisperWhisper via HuggingFace transformers (local/precise). Both produce identical JSON output. CLI entry point delegates to the chosen backend, which returns a normalized result that gets written as JSON.

**Tech Stack:** Python 3.10+, OpenAI SDK (>=1.12), PyTorch + HuggingFace transformers (custom fork for CrisperWhisper), argparse for CLI. Requires ffmpeg on PATH for local backend.

---

### Task 1: Project scaffolding and output schema

**Files:**
- Create: `tools/__init__.py`
- Create: `tools/transcribe/__init__.py`
- Create: `tools/transcribe/output.py`
- Create: `tools/transcribe/backends/__init__.py`
- Create: `tools/transcribe/requirements.txt`
- Create: `tools/transcribe/requirements-local.txt`

**Step 1: Create directory structure**

```bash
mkdir -p tools/transcribe/backends
```

**Step 2: Create `tools/__init__.py`**

Empty file. Required for package imports to work.

**Step 3: Create `tools/transcribe/__init__.py`**

Empty file.

**Step 4: Create `tools/transcribe/backends/__init__.py`**

Empty file.

**Step 5: Create `tools/transcribe/output.py`**

This module defines the output data structures and the JSON serialization logic. Both backends will return data in this format.

```python
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
```

**Step 6: Create `tools/transcribe/requirements.txt`**

```
openai>=1.12
```

**Step 7: Create `tools/transcribe/requirements-local.txt`**

```
torch>=2.0
torchaudio
soundfile
git+https://github.com/nyrahealth/transformers.git@crisper_whisper
```

**Step 8: Commit**

```bash
git add tools/
git commit -m "scaffold transcription tool with output schema"
```

---

### Task 2: OpenAI Whisper API backend

**Files:**
- Create: `tools/transcribe/backends/openai_backend.py`

**Step 1: Implement the OpenAI backend**

Key design notes:
- `response.segments` can be `None` even when requested — must handle gracefully with fallback
- OpenAI has a 25MB upload limit — validate before sending
- Word-to-segment assignment uses midpoint matching for robustness at segment boundaries

```python
"""OpenAI Whisper API backend for transcription."""

from __future__ import annotations

import os
import sys
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

    client = OpenAI()  # Uses OPENAI_API_KEY env var

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
            nearest = min(range(len(segments)), key=lambda i: abs(segments[i].start - w.start))
            result[nearest].append(w)
    return result
```

**Step 2: Commit**

```bash
git add tools/transcribe/backends/openai_backend.py
git commit -m "add OpenAI Whisper API transcription backend"
```

---

### Task 3: CrisperWhisper local backend

**Files:**
- Create: `tools/transcribe/backends/crisper_backend.py`

**Step 1: Implement the CrisperWhisper backend**

Key design notes:
- Uses full CrisperWhisper (not faster_CrisperWhisper) for guaranteed timestamp accuracy
- Language param needs Whisper token format `<|en|>`, not bare `"en"`
- `_adjust_pauses` is inlined to avoid cloning the CrisperWhisper repo
- `_build_segments` has max duration/word count fallback for languages without punctuation
- Warns user if running on CPU (will be very slow)
- Handles CUDA OOM with a helpful error message
- Caches the pipeline at module level to avoid reloading on repeated calls
- Validates pipeline output isn't garbage (known CrisperWhisper issue #17)
- Uses ffprobe for audio duration (avoids torchaudio/soundfile backend issues on Windows)

```python
"""CrisperWhisper local backend for transcription with precise timestamps and filler detection."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from tools.transcribe.output import Transcript, TranscriptMetadata, Segment, Word

# Filler pattern: CrisperWhisper marks fillers as [UH], [UM], etc.
_FILLER_PATTERN = re.compile(r"^\[.*\]$")

# Known filler tokens from CrisperWhisper
_FILLER_TOKENS = {"[UH]", "[UM]", "[AH]", "[ER]", "[HM]", "[HESITATION]"}

# Segment splitting limits for languages without punctuation
_MAX_SEGMENT_WORDS = 40
_MAX_SEGMENT_DURATION = 15.0  # seconds

# Unicode sentence-ending characters
_SENTENCE_ENDINGS = (".", "!", "?", "\u3002", "\uff01", "\uff1f")

# Module-level pipeline cache
_cached_pipe = None


def _adjust_pauses(pipeline_output: dict, split_threshold: float = 0.12) -> dict:
    """Distribute pauses between adjacent words.

    Reimplementation of CrisperWhisper's adjust_pauses_for_hf_pipeline_output.
    Splits pause duration evenly between adjacent chunks, capped at half the threshold.
    """
    chunks = list(pipeline_output.get("chunks", []))
    for i in range(len(chunks) - 1):
        current = chunks[i]
        next_chunk = chunks[i + 1]
        current_end = current["timestamp"][1]
        next_start = next_chunk["timestamp"][0]

        if current_end is None or next_start is None:
            continue

        pause = next_start - current_end
        if pause > 0:
            if pause > split_threshold:
                adjustment = split_threshold / 2
            else:
                adjustment = pause / 2
            current["timestamp"] = (current["timestamp"][0], current_end + adjustment)
            next_chunk["timestamp"] = (next_start - adjustment, next_chunk["timestamp"][1])

    pipeline_output["chunks"] = chunks
    return pipeline_output


def _load_pipeline(device: str = None):
    """Load CrisperWhisper model and return HF pipeline. Cached after first call."""
    global _cached_pipe
    if _cached_pipe is not None:
        return _cached_pipe

    import torch
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

    if device is None:
        device = "cuda:0" if torch.cuda.is_available() else "cpu"

    if device == "cpu":
        import warnings
        warnings.warn(
            "No CUDA GPU detected. CrisperWhisper on CPU will be very slow "
            "(10-50x realtime). Consider using the OpenAI API backend instead (remove --local)."
        )

    torch_dtype = torch.float16 if "cuda" in device else torch.float32

    model_id = "nyrahealth/CrisperWhisper"
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        model_id,
        torch_dtype=torch_dtype,
        low_cpu_mem_usage=True,
        use_safetensors=True,
    )
    model.to(device)

    processor = AutoProcessor.from_pretrained(model_id)

    pipe = pipeline(
        "automatic-speech-recognition",
        model=model,
        tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor,
        chunk_length_s=30,
        batch_size=16,
        return_timestamps="word",
        torch_dtype=torch_dtype,
        device=device,
    )

    _cached_pipe = pipe
    return pipe


def _get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    if not shutil.which("ffprobe"):
        # Fallback: estimate from last word timestamp
        return 0.0

    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", audio_path],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        data = json.loads(result.stdout)
        return float(data.get("format", {}).get("duration", 0.0))
    return 0.0


def transcribe(audio_path: str, language: str = "en") -> Transcript:
    """Transcribe audio using CrisperWhisper with precise word timestamps and filler detection."""
    import torch

    # Check ffmpeg availability
    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "ffmpeg is required for CrisperWhisper audio loading. "
            "Install it and add to PATH."
        )

    pipe = _load_pipeline()

    # Run transcription with CUDA OOM handling
    try:
        raw_output = pipe(
            audio_path,
            generate_kwargs={"language": f"<|{language}|>"},
        )
    except torch.cuda.OutOfMemoryError:
        raise RuntimeError(
            "GPU out of memory. CrisperWhisper requires ~4GB VRAM. "
            "Try closing other GPU applications or use the OpenAI API backend (remove --local)."
        )

    # Validate output isn't garbage (known CrisperWhisper issue)
    text = raw_output.get("text", "")
    if text and text.count("(") > len(text) * 0.3:
        raise RuntimeError(
            "CrisperWhisper produced invalid output (repeated characters). "
            "This is a known issue. Try: (1) update the transformers fork, "
            "(2) re-download the model, (3) use the OpenAI API backend as fallback."
        )

    # Adjust pause distribution
    output = _adjust_pauses(raw_output)

    # Build words from chunks
    chunks = output.get("chunks", [])
    words = []
    for chunk in chunks:
        chunk_text = chunk["text"].strip()
        start, end = chunk["timestamp"]
        if start is None or end is None:
            continue

        word_type = None
        if _FILLER_PATTERN.match(chunk_text) or chunk_text.upper() in _FILLER_TOKENS:
            word_type = "filler"

        words.append(Word(word=chunk_text, start=round(start, 3), end=round(end, 3), type=word_type))

    # Group words into segments
    segments = _build_segments(words)

    # Get duration (from ffprobe, fallback to last word end time)
    duration = _get_audio_duration(audio_path)
    if duration == 0.0 and words:
        duration = words[-1].end

    metadata = TranscriptMetadata(
        file=Path(audio_path).name,
        duration_seconds=round(duration, 2),
        backend="crisper_whisper",
        language=language,
    )

    return Transcript(metadata=metadata, segments=segments)


def _build_segments(words: list[Word], gap_threshold: float = 1.0) -> list[Segment]:
    """Group words into segments.

    Splits on: large gaps (>1s), sentence-ending punctuation with small gaps (>0.2s),
    or when a segment exceeds max word count / duration.
    """
    if not words:
        return []

    segments = []
    current_words = [words[0]]

    for i in range(1, len(words)):
        prev = words[i - 1]
        curr = words[i]
        gap = curr.start - prev.end

        # Split on sentence-ending punctuation (supports Unicode)
        ends_sentence = prev.word.rstrip("]").endswith(_SENTENCE_ENDINGS)

        # Split on segment size limits (fallback for languages without punctuation)
        segment_too_long = (
            len(current_words) >= _MAX_SEGMENT_WORDS
            or (curr.end - current_words[0].start) > _MAX_SEGMENT_DURATION
        )

        if gap > gap_threshold or (ends_sentence and gap > 0.2) or segment_too_long:
            seg_text = " ".join(w.word for w in current_words)
            segments.append(Segment(
                id=len(segments),
                start=current_words[0].start,
                end=current_words[-1].end,
                text=seg_text,
                words=list(current_words),
            ))
            current_words = [curr]
        else:
            current_words.append(curr)

    # Final segment
    if current_words:
        seg_text = " ".join(w.word for w in current_words)
        segments.append(Segment(
            id=len(segments),
            start=current_words[0].start,
            end=current_words[-1].end,
            text=seg_text,
            words=list(current_words),
        ))

    return segments
```

**Step 2: Commit**

```bash
git add tools/transcribe/backends/crisper_backend.py
git commit -m "add CrisperWhisper local transcription backend"
```

---

### Task 4: CLI entry point

**Files:**
- Create: `tools/transcribe/transcribe.py`

**Step 1: Implement the CLI**

Key design notes:
- Supports both `python tools/transcribe/transcribe.py` and `python -m tools.transcribe.transcribe`
- Uses `sys.path` hack for direct script execution
- Uses string manipulation for output path (`.with_suffix` breaks on Python <3.12 with compound suffixes)
- Validates empty files before dispatching

```python
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
```

**Step 2: Commit**

```bash
git add tools/transcribe/transcribe.py
git commit -m "add CLI entry point for transcription tool"
```

---

### Task 5: README documentation

**Files:**
- Create: `tools/transcribe/README.md`

**Step 1: Write usage documentation**

Must cover:
- Python 3.10+ requirement
- **OpenAI mode:** `pip install -r tools/transcribe/requirements.txt`, set `OPENAI_API_KEY`, 25MB file size limit
- **Local mode:** `pip install -r tools/transcribe/requirements-local.txt`, ffmpeg must be on PATH, CUDA GPU recommended (~4GB VRAM), HuggingFace account + model license acceptance at https://huggingface.co/nyrahealth/CrisperWhisper
- CLI usage examples
- Output JSON format with example
- Known issues: CrisperWhisper pipeline may produce garbage output (issue #17), CPU mode is very slow

**Step 2: Commit**

```bash
git add tools/transcribe/README.md
git commit -m "add transcription tool documentation"
```

---

### Task 6: Manual integration test

**Step 1: Test OpenAI API backend**

Requires: `OPENAI_API_KEY` set in environment, a short test audio file.

```bash
cd /c/Projects/DavinciMCP
pip install -r tools/transcribe/requirements.txt
python tools/transcribe/transcribe.py test_audio.wav
cat test_audio.transcript.json
```

Verify:
- JSON output has metadata with `backend: "openai_whisper"`
- Segments have start/end times
- Words within segments have start/end times
- No crash on empty response fields

**Step 2: Test OpenAI backend with oversized file**

```bash
python tools/transcribe/transcribe.py large_file.wav
```

Verify: Clear error message about 25MB limit.

**Step 3: Test CrisperWhisper backend**

Requires: CUDA GPU, HuggingFace account with model access, dependencies installed.

```bash
pip install -r tools/transcribe/requirements-local.txt
huggingface-cli login
python tools/transcribe/transcribe.py test_audio.wav --local
cat test_audio.transcript.json
```

Verify:
- JSON output has metadata with `backend: "crisper_whisper"`
- Words have precise timestamps
- Filler words (um, uh) marked with `"type": "filler"`
- Output is not garbage (repeated parentheses)

**Step 4: Commit any fixes discovered during testing**

---

## Execution Notes

- Tasks 1-4 are sequential (each builds on previous)
- Task 5 (README) can run in parallel with Task 4
- Task 6 requires user involvement (API key, GPU, audio file)
- Both `python tools/transcribe/transcribe.py` and `python -m tools.transcribe.transcribe` work
- CrisperWhisper requires accepting the model license at https://huggingface.co/nyrahealth/CrisperWhisper before first use
- ffmpeg must be installed and on PATH for local backend
