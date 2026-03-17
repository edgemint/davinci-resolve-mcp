# Timed Audio Transcription Tool — Design

## Purpose

Standalone CLI tool for high-quality audio transcription with precise word-level timestamps. Primary use case: feed the transcript to an LLM to identify segments to cut/clean up in video editing, with exact timing for each cut point.

## Architecture

Standalone tool at `tools/transcribe/` with two backends producing identical JSON output:

- **OpenAI Whisper API** — primary/easy mode, highest quality, minimal setup
- **Full CrisperWhisper** — local mode, best timestamp precision, filler word detection

```
tools/transcribe/
├── transcribe.py          # CLI entry point
├── backends/
│   ├── openai_backend.py  # OpenAI Whisper API
│   └── crisper_backend.py # Full CrisperWhisper (transformers)
├── output.py              # JSON output formatting
├── requirements.txt       # Base dependencies
├── requirements-local.txt # CrisperWhisper dependencies (torch, transformers fork)
└── README.md              # Setup + usage docs
```

## CLI Interface

```bash
# OpenAI API (default)
python tools/transcribe/transcribe.py recording.wav

# Local CrisperWhisper
python tools/transcribe/transcribe.py recording.wav --local

# Options
python tools/transcribe/transcribe.py recording.wav --local --language en --output transcript.json
```

## Output Format (JSON)

```json
{
  "metadata": {
    "file": "recording.wav",
    "duration_seconds": 342.5,
    "backend": "crisper_whisper",
    "language": "en",
    "timestamp": "2026-02-25T14:30:00Z"
  },
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 4.82,
      "text": "So today we're going to talk about, um, the new feature.",
      "words": [
        {"word": "So", "start": 0.0, "end": 0.28},
        {"word": "today", "start": 0.32, "end": 0.68},
        {"word": "[um]", "start": 2.10, "end": 2.55, "type": "filler"},
        {"word": "the", "start": 2.80, "end": 2.95},
        {"word": "new", "start": 2.98, "end": 3.22},
        {"word": "feature.", "start": 3.25, "end": 3.78}
      ]
    }
  ]
}
```

- Filler words (`um`, `uh`) marked with `"type": "filler"` (CrisperWhisper only)
- Gaps between words indicate pauses
- Both backends produce same JSON shape

## Dependencies

**API mode:** `openai`

**Local mode (separate requirements file):**
- `torch` + `torchaudio` (CUDA 12)
- Custom transformers fork: `git+https://github.com/nyrahealth/transformers.git@crisper_whisper`
- HuggingFace model: `nyrahealth/CrisperWhisper` (requires account + license)

## Hardware

- Local mode: ~3.2GB model, runs comfortably on 12GB RTX 4070
- Full CrisperWhisper (not faster_CrisperWhisper) for guaranteed timestamp accuracy

## Decisions

- Audio files only (no video extraction, no URL download)
- Single speaker (no diarization)
- JSON output only (no SRT/VTT)
- Full CrisperWhisper over faster_CrisperWhisper (timestamp accuracy is the whole point)
