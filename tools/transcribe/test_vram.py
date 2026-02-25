#!/usr/bin/env python3
"""VRAM benchmark for CrisperWhisper batch_size tuning.

Tests batch_size values 1, 2, 4, 8, 16 on a synthetic ~2-minute audio signal
and reports peak VRAM usage for each. Recommends the largest batch_size that
fits in available GPU memory.

Usage:
    python tools/transcribe/test_vram.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Support both direct execution and module execution (mirrors transcribe.py)
if __name__ == "__main__" and __package__ is None:
    _root = str(Path(__file__).resolve().parent.parent.parent)
    if _root not in sys.path:
        sys.path.insert(0, _root)

# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------

def _check_dependencies() -> None:
    missing = []

    try:
        import torch  # noqa: F401
    except ImportError:
        missing.append("torch")

    try:
        import numpy  # noqa: F401
    except ImportError:
        missing.append("numpy")

    try:
        import transformers  # noqa: F401
    except ImportError:
        missing.append("transformers")

    try:
        import accelerate  # noqa: F401
    except ImportError:
        missing.append("accelerate")

    if missing:
        print("ERROR: The following required packages are not installed:")
        for pkg in missing:
            print(f"  - {pkg}")
        print()
        print("Install them with:")
        print(f"  pip install {' '.join(missing)}")
        if "accelerate" in missing:
            print()
            print("Note: 'accelerate' is required by the transformers pipeline for")
            print("device placement. Without it, model loading will fail.")
        sys.exit(1)


_check_dependencies()

import torch
import numpy as np

# ---------------------------------------------------------------------------
# Synthetic audio generation
# ---------------------------------------------------------------------------

SAMPLE_RATE = 16_000      # Hz — Whisper's expected input sample rate
AUDIO_DURATION_S = 120    # seconds (~2 minutes)


def _make_synthetic_audio(duration_s: float = AUDIO_DURATION_S, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Generate a sine-wave audio signal that CrisperWhisper can process.

    Uses a 440 Hz tone mixed with a quieter 880 Hz tone to produce a
    non-trivial waveform. Normalized to float32 in [-1, 1].
    """
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False, dtype=np.float32)
    signal = 0.6 * np.sin(2 * np.pi * 440 * t) + 0.4 * np.sin(2 * np.pi * 880 * t)
    # Normalize
    peak = np.abs(signal).max()
    if peak > 0:
        signal /= peak
    return signal


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

def _load_model(device: str, torch_dtype: torch.dtype):
    """Load CrisperWhisper model and processor (no pipeline yet — batch_size varies)."""
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

    model_id = "nyrahealth/CrisperWhisper"
    print(f"  Loading model '{model_id}' ...")

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
    return model, processor


def _build_pipeline(model, processor, batch_size: int, device: str, torch_dtype: torch.dtype):
    """Construct a HF pipeline with a specific batch_size (mirrors crisper_backend.py)."""
    from transformers import pipeline

    return pipeline(
        "automatic-speech-recognition",
        model=model,
        tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor,
        chunk_length_s=30,
        batch_size=batch_size,
        return_timestamps="word",
        torch_dtype=torch_dtype,
        device=device,
    )


# ---------------------------------------------------------------------------
# VRAM benchmark
# ---------------------------------------------------------------------------

BATCH_SIZES = [1, 2, 4, 8, 16]


def _bytes_to_gib(n: int) -> float:
    return n / (1024 ** 3)


def _run_benchmark() -> None:
    if not torch.cuda.is_available():
        print("ERROR: No CUDA GPU detected. This benchmark requires a CUDA-capable GPU.")
        sys.exit(1)

    device = "cuda:0"
    torch_dtype = torch.float16

    gpu_name = torch.cuda.get_device_name(0)
    total_vram_gib = _bytes_to_gib(torch.cuda.get_device_properties(0).total_memory)
    print(f"GPU: {gpu_name}")
    print(f"Total VRAM: {total_vram_gib:.2f} GiB")
    print()

    # Generate synthetic audio once
    print(f"Generating synthetic audio ({AUDIO_DURATION_S}s at {SAMPLE_RATE} Hz) ...")
    audio = _make_synthetic_audio()
    print(f"  Audio shape: {audio.shape}  dtype: {audio.dtype}")
    print()

    # Load model once — it stays resident across all batch_size trials
    print("Loading CrisperWhisper model (this may take a minute on first run) ...")
    model, processor = _load_model(device, torch_dtype)

    # Measure baseline VRAM after model load (before any inference)
    torch.cuda.synchronize()
    baseline_vram = torch.cuda.memory_allocated(0)
    print(f"  Model baseline VRAM: {_bytes_to_gib(baseline_vram):.2f} GiB")
    print()

    # ---------------------------------------------------------------------------
    # Per-batch-size trials
    # ---------------------------------------------------------------------------
    results: list[dict] = []

    for batch_size in BATCH_SIZES:
        print(f"--- batch_size={batch_size} ---")

        # Clear allocator cache and reset peak stats before each trial
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(0)

        pipe = _build_pipeline(model, processor, batch_size, device, torch_dtype)

        try:
            # Run inference on the numpy array directly (HF pipeline accepts ndarray + sampling_rate)
            _ = pipe(
                {"array": audio, "sampling_rate": SAMPLE_RATE},
                generate_kwargs={"language": "<|en|>"},
            )

            torch.cuda.synchronize()
            peak_bytes = torch.cuda.max_memory_allocated(0)
            peak_gib = _bytes_to_gib(peak_bytes)
            inference_gib = _bytes_to_gib(peak_bytes - baseline_vram)

            print(f"  Peak VRAM:           {peak_gib:.2f} GiB")
            print(f"  Inference overhead:  {inference_gib:.2f} GiB (above model baseline)")
            print(f"  Status:              OK")
            results.append({
                "batch_size": batch_size,
                "ok": True,
                "peak_gib": peak_gib,
                "inference_overhead_gib": inference_gib,
            })

        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            print(f"  Status:              OOM (out of memory)")
            results.append({
                "batch_size": batch_size,
                "ok": False,
                "peak_gib": None,
                "inference_overhead_gib": None,
            })
            print("  Stopping — larger batch sizes will also OOM.")
            break

        print()

        # Clean up pipeline object between trials to free temporary buffers
        del pipe
        torch.cuda.empty_cache()

    # ---------------------------------------------------------------------------
    # Summary table
    # ---------------------------------------------------------------------------
    _print_summary(results, total_vram_gib)


def _print_summary(results: list[dict], total_vram_gib: float) -> None:
    col_w = [12, 14, 20, 8]
    header = (
        f"{'batch_size':<{col_w[0]}}"
        f"{'peak VRAM':>{col_w[1]}}"
        f"{'inference overhead':>{col_w[2]}}"
        f"{'status':>{col_w[3]}}"
    )
    divider = "-" * sum(col_w)

    print("=" * sum(col_w))
    print("SUMMARY")
    print("=" * sum(col_w))
    print(header)
    print(divider)

    best_ok: dict | None = None
    for r in results:
        if r["ok"]:
            peak_str = f"{r['peak_gib']:.2f} GiB"
            overhead_str = f"{r['inference_overhead_gib']:.2f} GiB"
            status_str = "OK"
            best_ok = r
        else:
            peak_str = "—"
            overhead_str = "—"
            status_str = "OOM"

        print(
            f"{r['batch_size']:<{col_w[0]}}"
            f"{peak_str:>{col_w[1]}}"
            f"{overhead_str:>{col_w[2]}}"
            f"{status_str:>{col_w[3]}}"
        )

    # Fill in skipped rows (never reached due to early OOM stop)
    tested_sizes = {r["batch_size"] for r in results}
    for bs in BATCH_SIZES:
        if bs not in tested_sizes:
            print(
                f"{bs:<{col_w[0]}}"
                f"{'—':>{col_w[1]}}"
                f"{'—':>{col_w[2]}}"
                f"{'skipped':>{col_w[3]}}"
            )

    print("=" * sum(col_w))
    print()

    if best_ok is None:
        print("RECOMMENDATION: No batch size succeeded. Your GPU may not have enough VRAM")
        print("for CrisperWhisper. Try closing other GPU applications and re-running.")
    else:
        recommended = best_ok["batch_size"]
        peak = best_ok["peak_gib"]
        headroom = total_vram_gib - peak
        print(f"RECOMMENDATION: Use batch_size={recommended}")
        print(f"  Peak VRAM at this setting: {peak:.2f} GiB / {total_vram_gib:.2f} GiB total")
        print(f"  Headroom remaining:        {headroom:.2f} GiB")
        print()
        print(f"  Set this in crisper_backend.py:")
        print(f"      batch_size={recommended},")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _run_benchmark()
