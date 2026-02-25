# Audio Transcription Tool

Fast, accurate audio transcription with word-level timestamps. Produces JSON suitable for video editing workflows—identify filler words, long pauses, or segments to cut.

**Requires:** Python 3.10+

---

## Installation

### OpenAI API Mode (Recommended for Speed)

```bash
pip install -r tools/transcribe/requirements.txt
export OPENAI_API_KEY="your-key-here"
```

- **Cost:** ~$0.006 per minute of audio
- **Limit:** 25 MB file size
- **Speed:** Fast (~10 seconds per minute of audio)

### Local Mode with CrisperWhisper (Recommended for Privacy)

```bash
pip install -r tools/transcribe/requirements-local.txt
```

**Requirements:**
- ffmpeg on PATH
- CUDA GPU recommended (~4 GB VRAM)
- HuggingFace account with model license accepted at [https://huggingface.co/nyrahealth/CrisperWhisper](https://huggingface.co/nyrahealth/CrisperWhisper)

**Performance:**
- GPU: ~1–2 seconds per minute of audio
- CPU: Very slow (not recommended)

---

## Usage

### Direct Execution

```bash
python tools/transcribe/transcribe.py recording.wav
python tools/transcribe/transcribe.py recording.wav --local
python tools/transcribe/transcribe.py recording.wav --local -o transcript.json
python tools/transcribe/transcribe.py recording.wav -l es  # Spanish
```

### As a Module

```python
from tools.transcribe.backends.openai_backend import transcribe

transcript = transcribe("recording.wav", language="en")
transcript.save("output.json")
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--local` | — | Use CrisperWhisper instead of OpenAI API |
| `--language`, `-l` | `en` | Language code (e.g., `en`, `es`, `fr`) |
| `--output`, `-o` | `{input}.transcript.json` | Output JSON path |

---

## Output Format

Generates a JSON file with segment-level and word-level timestamps:

```json
{
  "metadata": {
    "file": "recording.wav",
    "duration_seconds": 45.2,
    "backend": "openai",
    "language": "en",
    "timestamp": "2026-02-25T12:00:00+00:00"
  },
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 2.5,
      "text": "Hello, um, welcome.",
      "words": [
        { "word": "Hello", "start": 0.1, "end": 0.5 },
        { "word": "um", "start": 0.6, "end": 0.9, "type": "filler" },
        { "word": "welcome", "start": 1.2, "end": 2.4 }
      ]
    }
  ]
}
```

**Filler detection:** Words marked with `"type": "filler"` (um, uh, ah, etc.) can be identified for cleanup in video editing.

---

## Known Issues

- **CrisperWhisper pipeline garbage output** — The model may produce corrupted output in rare cases ([CrisperWhisper issue #17](https://github.com/nyrahealth/CrisperWhisper/issues/17)). Verify results on long files.
- **CPU mode is very slow** — Local transcription on CPU takes minutes per minute of audio. GPU is highly recommended.
- **File size limits** — OpenAI API: 25 MB max. For larger files, use local mode or split the file.

---

## Use Cases

- **Video editing:** Identify filler words (um, uh) and segments to cut/clean up
- **Accessibility:** Generate captions or transcripts with precise timestamps
- **Content analysis:** Feed to LLMs to summarize or extract key segments

Feed the JSON output to an LLM for intelligent segment identification.
