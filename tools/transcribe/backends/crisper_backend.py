"""CrisperWhisper local backend for transcription with precise timestamps and filler detection.

Features:
- Incremental saves: writes progress to a .partial.json after each chunk
- Resume support: resumes from partial file if interrupted
- Progress bar with ETA
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import sys
import time
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

# Chunking parameters
_CHUNK_LENGTH_S = 30.0
_STRIDE_S = 5.0  # overlap on each side

# Module-level caches
_cached_model = None
_cached_processor = None


# ---------------------------------------------------------------------------
# Audio loading
# ---------------------------------------------------------------------------

def _get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    if not shutil.which("ffprobe"):
        return 0.0
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", audio_path],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        data = json.loads(result.stdout)
        return float(data.get("format", {}).get("duration", 0.0))
    return 0.0


def _load_audio(audio_path: str) -> tuple:
    """Load audio file as numpy array at 16kHz. Returns (array, sample_rate)."""
    import numpy as np
    try:
        import librosa
        audio, sr = librosa.load(audio_path, sr=16000, mono=True)
        return audio, sr
    except ImportError:
        pass

    # Fallback: use ffmpeg to convert to raw PCM
    result = subprocess.run(
        ["ffmpeg", "-i", audio_path, "-f", "f32le", "-acodec", "pcm_f32le",
         "-ar", "16000", "-ac", "1", "-"],
        capture_output=True, timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed to decode audio: {result.stderr.decode()[-200:]}")

    audio = np.frombuffer(result.stdout, dtype=np.float32)
    return audio, 16000


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

def _load_model(device: str = None):
    """Load CrisperWhisper model and processor. Cached after first call."""
    global _cached_model, _cached_processor
    if _cached_model is not None:
        return _cached_model, _cached_processor

    import torch
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

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
    print("  Loading CrisperWhisper model...")
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        model_id,
        torch_dtype=torch_dtype,
        low_cpu_mem_usage=True,
        use_safetensors=True,
    )
    model.to(device)
    model.eval()

    processor = AutoProcessor.from_pretrained(model_id)
    print("  Model loaded.")

    _cached_model, _cached_processor = model, processor
    return model, processor


# ---------------------------------------------------------------------------
# Chunk-level transcription
# ---------------------------------------------------------------------------

def _transcribe_chunk(model, processor, audio_chunk, language: str, device: str) -> list[dict]:
    """Transcribe a single audio chunk. Returns list of word dicts with timestamps.

    Uses the model directly (not the pipeline) so we have full control over
    error handling and can process one chunk at a time.
    """
    import torch

    torch_dtype = torch.float16 if "cuda" in device else torch.float32

    inputs = processor(
        audio_chunk, sampling_rate=16000, return_tensors="pt"
    )
    input_features = inputs.input_features.to(device, dtype=torch_dtype)

    with torch.no_grad():
        try:
            predicted_ids = model.generate(
                input_features,
                language=f"<|{language}|>",
                return_timestamps=True,
                task="transcribe",
            )
        except RuntimeError as e:
            if "non-zero dimensions" in str(e) or "must match the size" in str(e):
                # Silent chunk — no speech detected
                return []
            raise

    # Decode with timestamps
    output = processor.batch_decode(predicted_ids, skip_special_tokens=False)[0]

    # Parse timestamps from token output
    words = _parse_whisper_tokens(output, processor)
    return words


def _parse_whisper_tokens(decoded: str, processor) -> list[dict]:
    """Parse word-level timestamps from Whisper's decoded output with special tokens.

    Whisper outputs text like: <|0.00|> hello <|0.50|><|0.50|> world <|1.20|>
    After regex split with a capturing group, the parts array alternates:
      [pre_text, timestamp, text, timestamp, text, timestamp, ...]
    Words are bounded by consecutive timestamp pairs.
    """
    # Match timestamp tokens like <|0.00|> or <|12.34|>
    timestamp_pattern = re.compile(r"<\|(\d+\.?\d*)\|>")

    parts = timestamp_pattern.split(decoded)
    # parts layout: [text_0, ts_1, text_2, ts_3, text_4, ts_5, ...]
    # Timestamps are at odd indices, text at even indices.
    # A word is: start=parts[i], text=parts[i+1], end=parts[i+2] where i is odd.

    words = []
    # Special tokens to skip
    skip_tokens = {"<|endoftext|>", "<|startoftranscript|>", "<|en|>",
                   "<|transcribe|>", "<|notimestamps|>"}

    # Iterate through timestamp pairs: i, i+2 are timestamps, i+1 is text between them
    i = 1  # Start at first timestamp (odd index)
    while i + 2 < len(parts):
        try:
            start = float(parts[i])
            text = parts[i + 1].strip()
            end = float(parts[i + 2])
        except (ValueError, IndexError):
            i += 2
            continue

        if text and text not in skip_tokens:
            # Clean any remaining special tokens from the text
            clean = re.sub(r"<\|[^|]*\|>", "", text).strip()
            if clean:
                words.append({"text": clean, "start": start, "end": end})

        i += 2  # Advance to next timestamp (which becomes the start of the next word)

    return words


# ---------------------------------------------------------------------------
# Partial file I/O (incremental saves + resume)
# ---------------------------------------------------------------------------

def _partial_path(output_path: str) -> str:
    """Get the path for the partial/incremental save file."""
    p = Path(output_path)
    return str(p.parent / (p.stem + ".partial.json"))


def _save_partial(path: str, completed_chunks: list[dict], metadata: dict) -> None:
    """Save incremental progress to a partial file."""
    data = {
        "metadata": metadata,
        "completed_chunks": completed_chunks,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _load_partial(path: str) -> tuple[list[dict], dict] | None:
    """Load partial progress. Returns (completed_chunks, metadata) or None."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data["completed_chunks"], data["metadata"]
    except (json.JSONDecodeError, KeyError):
        return None


def _cleanup_partial(path: str) -> None:
    """Remove partial file after successful completion."""
    p = Path(path)
    if p.exists():
        p.unlink()


# ---------------------------------------------------------------------------
# Progress display
# ---------------------------------------------------------------------------

def _format_duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 3600:
        return f"{seconds // 60}:{seconds % 60:02d}"
    return f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def _print_progress(chunk_idx: int, total_chunks: int, start_time: float, resumed_from: int = 0):
    elapsed = time.time() - start_time
    chunks_processed = chunk_idx - resumed_from + 1
    pct = min(100, ((chunk_idx + 1) / max(total_chunks, 1)) * 100)

    bar_width = 30
    filled = int(bar_width * pct / 100)
    bar = "█" * filled + "░" * (bar_width - filled)

    if chunks_processed > 0 and pct < 100:
        rate = elapsed / chunks_processed
        remaining = rate * (total_chunks - chunk_idx - 1)
        eta_str = _format_duration(remaining)
    elif pct >= 100:
        eta_str = "done"
    else:
        eta_str = "..."

    sys.stderr.write(
        f"\r  [{bar}] {pct:5.1f}%  "
        f"chunk {chunk_idx + 1}/{total_chunks}  "
        f"elapsed {_format_duration(elapsed)}  "
        f"ETA {eta_str}   "
    )
    sys.stderr.flush()


def _clear_progress():
    sys.stderr.write("\r" + " " * 80 + "\r")
    sys.stderr.flush()


# ---------------------------------------------------------------------------
# Pause adjustment
# ---------------------------------------------------------------------------

def _adjust_pauses(words: list[dict], split_threshold: float = 0.12) -> list[dict]:
    """Distribute pauses between adjacent words."""
    for i in range(len(words) - 1):
        current = words[i]
        next_word = words[i + 1]
        pause = next_word["start"] - current["end"]
        if pause > 0:
            adjustment = min(pause / 2, split_threshold / 2)
            current["end"] = current["end"] + adjustment
            next_word["start"] = next_word["start"] - adjustment
    return words


# ---------------------------------------------------------------------------
# Main transcribe function
# ---------------------------------------------------------------------------

def transcribe(audio_path: str, language: str = "en", output_path: str = None) -> Transcript:
    """Transcribe audio using CrisperWhisper with incremental saves and resume support."""
    import torch

    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "ffmpeg is required for CrisperWhisper audio loading. "
            "Install it and add to PATH."
        )

    # Determine output path for partial saves
    if output_path is None:
        output_path = str(Path(audio_path).parent / (Path(audio_path).stem + ".transcript.json"))
    partial = _partial_path(output_path)

    # Get audio duration and calculate chunks
    duration = _get_audio_duration(audio_path)
    if duration <= 0:
        raise RuntimeError(f"Could not determine audio duration for {audio_path}")

    step = _CHUNK_LENGTH_S - 2 * _STRIDE_S  # 20s effective step
    total_chunks = max(1, math.ceil(duration / step))

    mins, secs = divmod(int(duration), 60)
    print(f"  Audio: {mins}:{secs:02d}  |  {total_chunks} chunks  |  chunk={_CHUNK_LENGTH_S}s stride={_STRIDE_S}s")

    # Check for resumable partial file
    resumed_from = 0
    all_words = []
    existing = _load_partial(partial)
    if existing is not None:
        completed_chunks, partial_meta = existing
        if partial_meta.get("file") == Path(audio_path).name:
            resumed_from = len(completed_chunks)
            # Reconstruct words from completed chunks
            for chunk_data in completed_chunks:
                all_words.extend(chunk_data.get("words", []))
            print(f"  Resuming from chunk {resumed_from}/{total_chunks} ({len(all_words)} words so far)")
        else:
            print(f"  Partial file is for a different audio file, starting fresh.")

    # Load audio and model
    print("  Loading audio...")
    audio, sr = _load_audio(audio_path)
    audio_samples = len(audio)

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    model, processor = _load_model(device)

    # Prepare partial metadata
    meta = {
        "file": Path(audio_path).name,
        "duration_seconds": round(duration, 2),
        "language": language,
        "chunk_length_s": _CHUNK_LENGTH_S,
        "stride_s": _STRIDE_S,
    }

    # Collect completed chunks for partial saves (load existing or start fresh)
    if existing and partial_meta.get("file") == Path(audio_path).name:
        completed_chunks = existing[0]
    else:
        completed_chunks = []

    # Process each chunk
    start_time = time.time()
    chunk_samples = int(_CHUNK_LENGTH_S * sr)
    step_samples = int(step * sr)

    for chunk_idx in range(total_chunks):
        if chunk_idx < resumed_from:
            continue

        # Calculate chunk boundaries with stride overlap
        chunk_start_sample = chunk_idx * step_samples
        chunk_end_sample = min(chunk_start_sample + chunk_samples, audio_samples)
        chunk_start_time = chunk_start_sample / sr

        if chunk_start_sample >= audio_samples:
            break

        audio_chunk = audio[chunk_start_sample:chunk_end_sample]

        # Transcribe this chunk
        try:
            chunk_words = _transcribe_chunk(model, processor, audio_chunk, language, device)
        except torch.cuda.OutOfMemoryError:
            _clear_progress()
            # Save what we have so far
            _save_partial(partial, completed_chunks, meta)
            raise RuntimeError(
                f"GPU out of memory at chunk {chunk_idx + 1}/{total_chunks}. "
                f"Progress saved to {partial} — re-run to resume."
            )

        # Offset timestamps to absolute position in the audio
        for w in chunk_words:
            w["start"] = round(w["start"] + chunk_start_time, 3)
            w["end"] = round(w["end"] + chunk_start_time, 3)

        all_words.extend(chunk_words)

        # Save progress incrementally
        completed_chunks.append({
            "chunk_idx": chunk_idx,
            "start_time": round(chunk_start_time, 2),
            "words": chunk_words,
        })
        _save_partial(partial, completed_chunks, meta)

        _print_progress(chunk_idx, total_chunks, start_time, resumed_from)

    _clear_progress()
    elapsed = time.time() - start_time
    print(f"  Transcription complete in {_format_duration(elapsed)}")

    # Deduplicate words from overlapping strides
    all_words = _deduplicate_stride_words(all_words)

    # Adjust pauses
    all_words = _adjust_pauses(all_words)

    # Tag fillers
    words = []
    for w in all_words:
        text = w["text"].strip()
        word_type = None
        if _FILLER_PATTERN.match(text) or text.upper() in _FILLER_TOKENS:
            word_type = "filler"
        words.append(Word(word=text, start=w["start"], end=w["end"], type=word_type))

    # Group into segments
    segments = _build_segments(words)

    # Clean up partial file
    _cleanup_partial(partial)

    metadata = TranscriptMetadata(
        file=Path(audio_path).name,
        duration_seconds=round(duration, 2),
        backend="crisper_whisper",
        language=language,
    )

    return Transcript(metadata=metadata, segments=segments)


# ---------------------------------------------------------------------------
# Stride deduplication
# ---------------------------------------------------------------------------

def _deduplicate_stride_words(words: list[dict]) -> list[dict]:
    """Remove duplicate words caused by overlapping stride regions.

    When chunks overlap, the same words can appear in both chunks.
    Keep the version with the earlier start time and skip near-duplicates.
    """
    if not words:
        return []

    # Sort by start time
    words.sort(key=lambda w: w["start"])

    deduped = [words[0]]
    for w in words[1:]:
        prev = deduped[-1]
        # Skip if this word overlaps significantly with the previous one
        # (same text within 0.3s is considered a duplicate)
        if (w["text"].strip().lower() == prev["text"].strip().lower()
                and abs(w["start"] - prev["start"]) < 0.3):
            continue
        # Skip if this word starts before the previous word ends (overlap)
        if w["start"] < prev["end"] - 0.05:
            continue
        deduped.append(w)

    return deduped


# ---------------------------------------------------------------------------
# Segment building
# ---------------------------------------------------------------------------

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

        ends_sentence = prev.word.rstrip("]").endswith(_SENTENCE_ENDINGS)

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
