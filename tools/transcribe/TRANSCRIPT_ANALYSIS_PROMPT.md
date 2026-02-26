# Transcript Analysis: Two-Pass Cut List Generation

You are an agent tasked with analyzing a spoken-word transcript to produce a **cut list** — a list of sections that should be removed during editing (repeated takes, filler words, misspoken words, false starts, stammering, etc.).

## Input

You will be given a `.transcript.json` file produced by CrisperWhisper or OpenAI Whisper. It has this structure:

```json
{
  "metadata": { "file": "recording.wav", "duration_seconds": 1504.0, "backend": "crisper_whisper", "language": "en" },
  "segments": [
    {
      "id": 0, "start": 2.36, "end": 16.1,
      "text": "The full segment text...",
      "words": [
        { "word": "The", "start": 2.36, "end": 2.67 },
        { "word": "[UH]", "start": 5.1, "end": 5.3, "type": "filler" }
      ]
    }
  ]
}
```

Key features: word-level timestamps (`start`/`end` in seconds), optional `"type": "filler"` on detected filler words, segment-level grouping.

## Output

Two files alongside the transcript:
- `<name>.cutlist.json` — machine-readable cut list
- `<name>.cutlist.md` — human-readable Markdown report

## Method: Two-Pass Hybrid

### Pass 1: Mechanical Analysis (run the script)

Run the existing analysis tool:

```bash
cd <project_root>
python tools/transcribe/analyze.py <path_to_transcript.json> --pass1-only
```

This runs 6 programmatic detectors on the full transcript and outputs a preliminary cut list. The detectors are:

| Detector | What it catches | Confidence |
|----------|----------------|------------|
| **Fillers** | Words tagged `type: "filler"` + regex match on `um, uh, uhh, umm, hmm, hm, ah, er` | HIGH |
| **Hallucinations** | Segments with >8 words/sec (impossibly fast) or reversed timestamps | HIGH |
| **Timestamp artifacts** | Single words spanning >3 seconds (dead air / timestamp padding) | MEDIUM |
| **Stammers** | Consecutive identical words (normalized). Skips intentional emphasis (both have commas). Cuts first occurrence. | MEDIUM |
| **False starts** | 1-5 word phrase at sentence boundary followed by ≥0.8s pause | MEDIUM |
| **Retakes** | 3-8 word N-gram repeated within 15 seconds. Cuts first occurrence. | HIGH |

Pass 1 output is printed to console and saved to the cutlist files. Review it before proceeding.

### Pass 2: Semantic Analysis (you do this)

Pass 2 catches what mechanical detection cannot: repeated takes with different wording, abandoned sentences, contextually misspoken words, and incoherent passages.

#### Step 1: Generate chunks

```bash
python tools/transcribe/analyze.py <path_to_transcript.json> --dump-chunks
```

This prints chunk prompts to stdout. Alternatively, generate them programmatically:

```python
from tools.transcribe.analyze import load_transcript
from tools.transcribe.analyzers.models import AnalysisConfig
from tools.transcribe.analyzers.pass1 import run_pass1
from tools.transcribe.analyzers.pass2 import chunk_transcript, build_chunk_prompt

transcript = load_transcript("path/to/file.transcript.json")
config = AnalysisConfig()
pass1_cuts = run_pass1(transcript, config)
chunks = chunk_transcript(transcript, config, pass1_cuts)

for chunk in chunks:
    prompt = build_chunk_prompt(chunk, len(chunks))
    # dispatch this prompt to an LLM agent
```

Chunking splits the transcript into ~2.5-minute segments at segment boundaries, with 2-segment overlap for context. Each chunk includes Pass 1 findings so the LLM avoids duplicating mechanical catches.

#### Step 2: Analyze each chunk

Dispatch each chunk prompt to a lightweight LLM agent (Haiku is sufficient). **Run all chunks in parallel** — they are independent.

Each agent receives a self-contained prompt and must return a JSON array of findings. The prompt instructs the LLM to look for:

| Issue type | Description | What to flag |
|-----------|-------------|-------------|
| **REPEATED_TAKE** | Same idea expressed twice with different wording | Flag FIRST attempt (keep second/cleaner version) |
| **ABANDONED** | Speaker starts a thought, stops, restarts differently | Flag the abandoned fragment only |
| **MISSPOKEN** | Word that doesn't fit context (wrong word, malapropism) | Flag for human review — don't auto-cut |
| **INCOHERENT** | Passage doesn't flow logically with surroundings | Flag the incoherent span |

Expected response format from each agent:

```json
[
  {
    "start": 173.78,
    "end": 178.22,
    "reason": "MISSPOKEN",
    "flagged_text": "That he's what laughing about it privately",
    "explanation": "\"what\" misplaced; should be \"just laughing\" or similar",
    "confidence": "high"
  }
]
```

#### Step 3: Parse and merge

Use the response parser to convert agent outputs to Cut objects, then merge with Pass 1:

```python
from tools.transcribe.analyzers.pass2 import parse_chunk_response
from tools.transcribe.analyzers.merger import build_cut_list
from tools.transcribe.analyzers.report import generate_report

pass2_cuts = []
for chunk, response_text in zip(chunks, agent_responses):
    pass2_cuts.extend(parse_chunk_response(response_text, chunk))

cut_list = build_cut_list(
    source_file=transcript.metadata.file,
    duration=transcript.metadata.duration_seconds,
    config=config,
    pass1_cuts=pass1_cuts,
    pass2_cuts=pass2_cuts,
    pass1_stats={"segments_analyzed": len(transcript.segments), "words_analyzed": n_words, "cuts_found": len(pass1_cuts)},
    pass2_stats={"chunks": len(chunks), "cuts_found": len(pass2_cuts)},
)

cut_list.save_json("output.cutlist.json")
with open("output.cutlist.md", "w") as f:
    f.write(generate_report(cut_list))
```

Merge rules:
- Overlapping cuts (>50% of shorter duration) are merged, keeping higher confidence
- Adjacent cuts (<0.3s gap) are merged
- Pass 1 mechanical reasons take priority over Pass 2 semantic reasons
- Explanations are combined with ` | `

## Quick-Reference: Full Pipeline in One Shot

For an agent running the entire pipeline end-to-end:

1. **Run Pass 1:** `python tools/transcribe/analyze.py <transcript.json> --pass1-only`
2. **Generate chunks** programmatically (see Step 1 above)
3. **Dispatch 10 parallel Haiku agents**, one per chunk, each receiving `build_chunk_prompt()` output
4. **Collect responses**, parse with `parse_chunk_response()`, merge with `build_cut_list()`
5. **Save** JSON + Markdown report
6. **Print summary** to user: total cuts, total cut time, breakdown by reason/confidence

## Configuration (AnalysisConfig defaults)

| Parameter | Default | What it controls |
|-----------|---------|-----------------|
| `pause_retake_threshold` | 1.5s | Minimum pause to flag as retake boundary |
| `pause_notable_threshold` | 0.8s | Minimum pause to annotate |
| `false_start_max_words` | 5 | Max words in an abandoned phrase |
| `false_start_min_gap` | 0.8s | Minimum gap after phrase to flag as false start |
| `hallucination_wps_threshold` | 8.0 | Words/sec above this = hallucinated segment |
| `artifact_word_duration` | 3.0s | Single word longer than this = timestamp artifact |
| `chunk_duration` | 150.0s | Target chunk size for Pass 2 (~2.5 minutes) |
| `overlap_segments` | 2 | Context segments borrowed from adjacent chunks |

## Confidence Guide

| Level | Meaning | Action |
|-------|---------|--------|
| **HIGH** | Clear mechanical match or obvious semantic issue | Safe to cut without listening |
| **MEDIUM** | Heuristic match or borderline case | Spot-check the audio before cutting |
| **LOW** | Ambiguous; LLM unsure | Listen to the audio and decide manually |

## File Locations

```
tools/transcribe/
    analyze.py              # CLI entry point
    analyzers/
        models.py           # Cut, CutList, AnalysisConfig dataclasses
        pass1.py            # 6 mechanical detectors
        pass2.py            # Chunking, prompt building, response parsing
        merger.py           # Merge Pass 1 + Pass 2, deduplicate
        report.py           # Markdown report generation
```
