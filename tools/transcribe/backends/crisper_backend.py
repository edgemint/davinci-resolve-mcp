"""CrisperWhisper local backend for transcription with precise timestamps and filler detection.

Features:
- Incremental saves: writes progress to a .partial.json after each segment
- Resume support: resumes from partial file if interrupted
- Progress bar with ETA
- Uses HF pipeline for proper word-level timestamp extraction
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import sys
import time
import warnings
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

# Outer-level segment size for progress tracking (seconds)
# The pipeline handles its own internal 30s chunking; we split the audio into
# larger segments (~5 min each) to show progress and save incrementally.
_SEGMENT_LENGTH_S = 300.0  # 5 minutes

# Module-level caches
_cached_pipe = None
_cached_pipe_fallback = None


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
# Pipeline construction
# ---------------------------------------------------------------------------

def _build_pipeline(return_timestamps="word"):
    """Build HF ASR pipeline for CrisperWhisper. Cached after first call."""
    import torch
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    torch_dtype = torch.float16 if "cuda" in device else torch.float32

    if device == "cpu":
        warnings.warn(
            "No CUDA GPU detected. CrisperWhisper on CPU will be very slow "
            "(10-50x realtime). Consider using the OpenAI API backend instead (remove --local)."
        )

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

    pipe = pipeline(
        "automatic-speech-recognition",
        model=model,
        tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor,
        chunk_length_s=30,
        batch_size=1,
        return_timestamps=return_timestamps,
        torch_dtype=torch_dtype,
        device=device,
    )
    return pipe


def _get_pipeline():
    """Get or create word-level timestamp pipeline."""
    global _cached_pipe
    if _cached_pipe is None:
        _cached_pipe = _build_pipeline(return_timestamps="word")
    return _cached_pipe


def _get_fallback_pipeline():
    """Get or create segment-level timestamp pipeline (fallback for silent chunks)."""
    global _cached_pipe_fallback
    if _cached_pipe_fallback is None:
        # Reuse the model from the primary pipeline to avoid loading twice
        pipe = _get_pipeline()
        from transformers import pipeline as make_pipeline
        _cached_pipe_fallback = make_pipeline(
            "automatic-speech-recognition",
            model=pipe.model,
            tokenizer=pipe.tokenizer,
            feature_extractor=pipe.feature_extractor,
            chunk_length_s=30,
            batch_size=1,
            return_timestamps=True,  # segment-level only
            torch_dtype=pipe.torch_dtype,
            device=pipe.device,
        )
    return _cached_pipe_fallback


# ---------------------------------------------------------------------------
# Segment-level transcription via pipeline
# ---------------------------------------------------------------------------

def _transcribe_segment(audio_segment, sr: int, language: str) -> list[dict]:
    """Transcribe an audio segment using the HF pipeline.

    Returns a list of word dicts: [{"text": str, "start": float, "end": float}, ...]

    Falls back to segment-level timestamps if word-level extraction fails
    (e.g., on silent audio chunks).
    """
    pipe = _get_pipeline()

    try:
        result = pipe(
            {"array": audio_segment, "sampling_rate": sr},
            generate_kwargs={"language": f"<|{language}|>"},
        )
    except RuntimeError as e:
        err_msg = str(e).lower()
        # Word-level timestamp extraction can fail in several ways:
        # - "non-zero dimensions" (empty token output from silent chunks)
        # - "must match the existing size" (tensor shape mismatch)
        # - "_extract_token_timestamps" related errors
        # Fall back to segment-level timestamps in all these cases.
        if any(phrase in err_msg for phrase in (
            "non-zero dimensions",
            "must match the",
            "extract_token_timestamps",
            "expanded size",
            "tensor",
        )):
            warnings.warn(
                "Word-level timestamp extraction failed (likely silent/problematic audio). "
                "Retrying with segment-level timestamps."
            )
            fallback = _get_fallback_pipeline()
            result = fallback(
                {"array": audio_segment, "sampling_rate": sr},
                generate_kwargs={"language": f"<|{language}|>"},
            )
        else:
            raise

    # Extract words from pipeline output
    words = []
    chunks = result.get("chunks", [])
    for chunk in chunks:
        text = chunk.get("text", "").strip()
        ts = chunk.get("timestamp", (None, None))
        if text and ts and ts[0] is not None:
            start = ts[0]
            end = ts[1] if ts[1] is not None else start + 0.5
            # Pipeline with return_timestamps="word" gives one word per chunk.
            # Pipeline with return_timestamps=True gives full segments —
            # split them into individual words with interpolated timestamps.
            if " " in text:
                # Segment-level: split into words with interpolated timestamps
                segment_words = text.split()
                seg_duration = end - start
                word_duration = seg_duration / len(segment_words) if segment_words else 0
                for j, w in enumerate(segment_words):
                    w_start = round(start + j * word_duration, 3)
                    w_end = round(start + (j + 1) * word_duration, 3)
                    words.append({"text": w, "start": w_start, "end": w_end})
            else:
                words.append({"text": text, "start": round(start, 3), "end": round(end, 3)})

    return words


# ---------------------------------------------------------------------------
# Partial file I/O (incremental saves + resume)
# ---------------------------------------------------------------------------

def _partial_path(output_path: str) -> str:
    """Get the path for the partial/incremental save file."""
    p = Path(output_path)
    return str(p.parent / (p.stem + ".partial.json"))


def _save_partial(path: str, completed_segments: list[dict], metadata: dict) -> None:
    """Save incremental progress to a partial file."""
    data = {
        "metadata": metadata,
        "completed_segments": completed_segments,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _load_partial(path: str) -> tuple[list[dict], dict] | None:
    """Load partial progress. Returns (completed_segments, metadata) or None."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Support both old "completed_chunks" and new "completed_segments" key
        segments = data.get("completed_segments", data.get("completed_chunks", []))
        return segments, data["metadata"]
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


def _print_progress(seg_idx: int, total_segs: int, start_time: float, resumed_from: int = 0):
    elapsed = time.time() - start_time
    segs_processed = seg_idx - resumed_from + 1
    pct = min(100, ((seg_idx + 1) / max(total_segs, 1)) * 100)

    bar_width = 30
    filled = int(bar_width * pct / 100)
    bar = "\u2588" * filled + "\u2591" * (bar_width - filled)

    if segs_processed > 0 and pct < 100:
        rate = elapsed / segs_processed
        remaining = rate * (total_segs - seg_idx - 1)
        eta_str = _format_duration(remaining)
    elif pct >= 100:
        eta_str = "done"
    else:
        eta_str = "..."

    sys.stderr.write(
        f"\r  [{bar}] {pct:5.1f}%  "
        f"segment {seg_idx + 1}/{total_segs}  "
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
    """Transcribe audio using CrisperWhisper with incremental saves and resume support.

    Splits the audio into ~5-minute segments, runs the HF pipeline on each,
    saves progress after each segment, and shows a progress bar.
    """
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

    # Get audio duration
    duration = _get_audio_duration(audio_path)
    if duration <= 0:
        raise RuntimeError(f"Could not determine audio duration for {audio_path}")

    total_segments = max(1, math.ceil(duration / _SEGMENT_LENGTH_S))

    mins, secs = divmod(int(duration), 60)
    print(f"  Audio: {mins}:{secs:02d}  |  {total_segments} segments of ~{int(_SEGMENT_LENGTH_S)}s")

    # Check for resumable partial file
    resumed_from = 0
    all_words = []
    existing = _load_partial(partial)
    if existing is not None:
        completed_segments, partial_meta = existing
        if partial_meta.get("file") == Path(audio_path).name:
            resumed_from = len(completed_segments)
            for seg_data in completed_segments:
                all_words.extend(seg_data.get("words", []))
            print(f"  Resuming from segment {resumed_from}/{total_segments} ({len(all_words)} words so far)")
        else:
            print(f"  Partial file is for a different audio file, starting fresh.")
            completed_segments = []
    else:
        completed_segments = []

    # Load audio
    print("  Loading audio...")
    audio, sr = _load_audio(audio_path)
    audio_samples = len(audio)

    # Initialize pipeline (loads model)
    _ = _get_pipeline()

    # Prepare partial metadata
    meta = {
        "file": Path(audio_path).name,
        "duration_seconds": round(duration, 2),
        "language": language,
        "segment_length_s": _SEGMENT_LENGTH_S,
    }

    # Process each segment
    start_time = time.time()
    segment_samples = int(_SEGMENT_LENGTH_S * sr)

    for seg_idx in range(total_segments):
        if seg_idx < resumed_from:
            continue

        seg_start_sample = seg_idx * segment_samples
        seg_end_sample = min(seg_start_sample + segment_samples, audio_samples)
        seg_start_time = seg_start_sample / sr

        if seg_start_sample >= audio_samples:
            break

        audio_segment = audio[seg_start_sample:seg_end_sample]

        # Transcribe this segment using the pipeline
        try:
            seg_words = _transcribe_segment(audio_segment, sr, language)
        except (torch.cuda.OutOfMemoryError, RuntimeError) as e:
            if isinstance(e, RuntimeError) and "out of memory" not in str(e).lower():
                raise  # Not an OOM error, re-raise
            _clear_progress()
            _save_partial(partial, completed_segments, meta)
            raise RuntimeError(
                f"GPU out of memory at segment {seg_idx + 1}/{total_segments}. "
                f"Progress saved to {partial} — re-run to resume."
            ) from e

        # Offset timestamps to absolute position in the audio
        for w in seg_words:
            w["start"] = round(w["start"] + seg_start_time, 3)
            w["end"] = round(w["end"] + seg_start_time, 3)

        all_words.extend(seg_words)

        # Save progress incrementally
        completed_segments.append({
            "segment_idx": seg_idx,
            "start_time": round(seg_start_time, 2),
            "words": seg_words,
        })
        _save_partial(partial, completed_segments, meta)

        _print_progress(seg_idx, total_segments, start_time, resumed_from)

    _clear_progress()
    elapsed = time.time() - start_time
    print(f"  Transcription complete in {_format_duration(elapsed)}")

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
