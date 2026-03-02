# Audio Enhance MCP — Design

**Date:** 2026-03-02
**Status:** Approved

## Purpose

Standalone MCP server that gives an LLM (Claude) a set of audio quality tools for dialogue and voiceover enhancement. The LLM can call atomic transform tools for manual control, or call a single `auto_enhance` tool that runs an internal optimization loop and returns the best result with a full step log.

Primary use case: improve raw dialogue/voiceover audio quality before or during video editing, with an objective composite score so the agent has a measurable standard to optimize toward.

## Project Location

Standalone repo at `C:/Projects/AudioEnhanceMCP/` — not part of DavinciMCP.

## Architecture

```
AudioEnhanceMCP/
├── server.py              # FastMCP entry point, tool definitions
├── score.py               # Composite scoring: DNSMOS + STOI → weighted score
├── optimizer.py           # Auto-enhance loop (greedy search + plateau detection)
├── transforms/
│   ├── resemble.py        # Denoise + Enhance wrappers (C:/Projects/resemble)
│   ├── loudness.py        # Loudness normalization (pyloudnorm, target -16 LUFS)
│   └── noise_reduce.py    # Spectral noise reduction (noisereduce)
├── requirements.txt
└── README.md
```

## MCP Tools (6)

| Tool | Description |
|---|---|
| `score_audio` | Returns DNSMOS (SIG, BAK) + STOI + composite score |
| `denoise_audio` | Resemble Enhance — denoise-only mode |
| `enhance_audio` | Resemble Enhance — full enhance, tunable `lambd` and `tau` |
| `normalize_loudness` | Normalize to target LUFS (default -16 for dialogue) |
| `reduce_noise` | Spectral noise reduction via `noisereduce` |
| `auto_enhance` | Full optimization loop — returns best file + per-round log |

All tools that produce audio write to caller-specified `output_path`. The original file is never overwritten.

## Composite Score

Three components, weighted toward dialogue priorities:

| Metric | Measures | Weight |
|---|---|---|
| DNSMOS SIG | Speech signal quality (clarity, naturalness) | 40% |
| DNSMOS BAK | Background noise suppression | 35% |
| STOI | Intelligibility (words remain understandable) | 25% |

All components normalized to 0–1 before weighting. Final composite score is 0–1. Score ≥ 0.90 triggers early stop in the optimizer.

No reference file required — DNSMOS and STOI are both no-reference metrics.

If a scoring dependency is missing, that component returns `null` and the remaining components are renormalized to fill its weight.

## Optimizer Loop (`auto_enhance`)

Greedy search over a predefined recipe space.

**Round 1 — recipe sweep (run in parallel):**

| Recipe | Parameters |
|---|---|
| denoise_only | Resemble denoise mode |
| enhance_light | lambd=0.3, tau=0.5 |
| enhance_medium | lambd=0.5, tau=0.5 |
| enhance_strong | lambd=0.7, tau=0.5 |
| normalize_only | -16 LUFS |
| denoise + normalize | denoise, then -16 LUFS |
| enhance_medium + normalize | lambd=0.5, then -16 LUFS |

**Round 2+ — refinement around winner:**
Generate parameter variations around the winning recipe (e.g. if `enhance_medium` won, try `lambd=0.4`, `lambd=0.6`, varied `tau`). Always applied to the original file — never chained — to avoid accumulating artifacts.

**Stopping conditions (first triggered wins):**
- Score improvement < 0.02 between rounds → plateau
- Max rounds reached (default 5, configurable)
- Composite score ≥ 0.90 → threshold met

**Return value:**
```json
{
  "output_path": "...",
  "baseline_score": 0.61,
  "final_score": 0.79,
  "improvement": 0.18,
  "stop_reason": "plateau",
  "log": [
    { "round": 1, "recipe": "enhance_medium+normalize", "score": 0.79 },
    { "round": 2, "recipe": "enhance_medium(lambd=0.6)+normalize", "score": 0.78 }
  ]
}
```

## Tool Interfaces

```python
score_audio(input_path: str)
  → { sig: float, bak: float, stoi: float, composite: float }

denoise_audio(input_path: str, output_path: str)
  → { output_path: str, composite_score: float }

enhance_audio(input_path: str, output_path: str, lambd: float = 0.5, tau: float = 0.5)
  → { output_path: str, composite_score: float }

normalize_loudness(input_path: str, output_path: str, target_lufs: float = -16.0)
  → { output_path: str, composite_score: float }

reduce_noise(input_path: str, output_path: str)
  → { output_path: str, composite_score: float }

auto_enhance(input_path: str, output_path: str, max_rounds: int = 5)
  → { output_path, baseline_score, final_score, improvement, stop_reason, log }
```

## Dependencies

- `fastmcp` — MCP server framework
- `torch` — required by Resemble Enhance
- `resemble-enhance` — from `C:/Projects/resemble` (local clone)
- `noisereduce` — spectral noise reduction
- `pyloudnorm` — LUFS loudness normalization
- `pystoi` — STOI intelligibility metric
- `dnsmos` or `speechmos` — DNSMOS scoring (Microsoft model)
- `soundfile` — audio I/O
- `numpy` — array ops

## What's Out of Scope (for now)

- Batch/folder processing (single file only)
- EQ, compression, de-reverb (can be added as future transforms)
- Integration with DavinciMCP or DaVinci Resolve directly
- Audio format conversion (assume WAV input/output)
