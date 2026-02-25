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
