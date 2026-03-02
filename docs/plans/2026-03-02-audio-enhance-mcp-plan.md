# Audio Enhance MCP — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a standalone FastMCP server exposing 6 audio enhancement tools for dialogue/voiceover quality improvement, with an auto-optimize loop driven by DNSMOS composite scoring.

**Architecture:** Standalone Python project at C:/Projects/AudioEnhanceMCP/. Six MCP tools: 4 atomic transforms (denoise, enhance, normalize, reduce_noise), 1 scorer, 1 auto_enhance optimizer loop. Transforms wrap local Resemble Enhance + noisereduce + pyloudnorm. Optimizer runs greedy search over preset recipes, stops at plateau/max-rounds/threshold.

**Tech Stack:** Python 3.10+, FastMCP, speechmos (DNSMOS), resemble-enhance (local), noisereduce, pyloudnorm, soundfile, librosa, torch

---

## Task 1: Project Bootstrap

**Goal:** Create the full directory skeleton, dependencies, and git repo. No implementation code yet.

### Step 1.1 — Create directory structure

```bash
mkdir -p C:/Projects/AudioEnhanceMCP/transforms
mkdir -p C:/Projects/AudioEnhanceMCP/tests
cd C:/Projects/AudioEnhanceMCP
git init
```

### Step 1.2 — Create `requirements.txt`

File: `C:/Projects/AudioEnhanceMCP/requirements.txt`

```
fastmcp>=0.1.0
torch>=2.0.0
torchaudio>=2.0.0
noisereduce>=3.0.0
pyloudnorm>=0.1.1
speechmos>=0.1.0
soundfile>=0.12.1
numpy>=1.24.0
librosa>=0.10.0
pytest>=7.0.0
```

Note: `resemble-enhance` is loaded via sys.path injection from `C:/Projects/resemble/` — it is NOT listed in requirements.txt because it is a local clone, not a pip package.

### Step 1.3 — Create `transforms/__init__.py`

File: `C:/Projects/AudioEnhanceMCP/transforms/__init__.py`

```python
# transforms package
```

### Step 1.4 — Create `tests/__init__.py`

File: `C:/Projects/AudioEnhanceMCP/tests/__init__.py`

```python
# tests package
```

### Step 1.5 — Create `.gitignore`

File: `C:/Projects/AudioEnhanceMCP/.gitignore`

```
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
dist/
build/
*.wav
*.mp3
*.flac
*.ogg
.pytest_cache/
.DS_Store
Thumbs.db
```

### Step 1.6 — Verify structure

```bash
find C:/Projects/AudioEnhanceMCP -type f
```

Expected output:
```
C:/Projects/AudioEnhanceMCP/.gitignore
C:/Projects/AudioEnhanceMCP/requirements.txt
C:/Projects/AudioEnhanceMCP/transforms/__init__.py
C:/Projects/AudioEnhanceMCP/tests/__init__.py
```

### Step 1.7 — Initial commit

```bash
cd C:/Projects/AudioEnhanceMCP
git add .gitignore requirements.txt transforms/__init__.py tests/__init__.py
git commit -m "Initial project scaffold"
```

---

## Task 2: Scoring Module (`score.py`)

**Goal:** Implement `score_audio()` using DNSMOS via `speechmos`. Weighted composite: SIG 40%, BAK 35%, OVRL 25%, each normalized from [1,5] to [0,1].

### Step 2.1 — Write the test first

File: `C:/Projects/AudioEnhanceMCP/tests/test_score.py`

```python
import numpy as np
import soundfile as sf
import tempfile
import os
import pytest
from score import load_audio, resample_to_16k, score_audio


def make_wav(duration=2.0, sr=44100, noise_scale=0.0, path=None):
    """Generate a sine wave with optional white noise, save to WAV, return path."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    sine = 0.5 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    if noise_scale > 0:
        sine += (np.random.randn(len(t)) * noise_scale).astype(np.float32)
    if path is None:
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
    sf.write(path, sine, sr)
    return path


class TestLoadAudio:
    def test_returns_array_and_sr(self):
        path = make_wav()
        try:
            audio, sr = load_audio(path)
            assert isinstance(audio, np.ndarray)
            assert sr == 44100
            assert audio.ndim == 1  # mono
        finally:
            os.unlink(path)

    def test_stereo_converted_to_mono(self):
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        stereo = np.random.randn(44100, 2).astype(np.float32) * 0.1
        sf.write(path, stereo, 44100)
        try:
            audio, sr = load_audio(path)
            assert audio.ndim == 1
        finally:
            os.unlink(path)


class TestResampleTo16k:
    def test_resamples_correctly(self):
        audio = np.random.randn(44100).astype(np.float32) * 0.1
        out = resample_to_16k(audio, sr=44100)
        assert len(out) == 16000
        assert out.dtype == np.float32

    def test_already_16k_unchanged(self):
        audio = np.random.randn(16000).astype(np.float32) * 0.1
        out = resample_to_16k(audio, sr=16000)
        assert len(out) == 16000


class TestScoreAudio:
    def test_returns_expected_keys(self):
        path = make_wav(noise_scale=0.0)
        try:
            result = score_audio(path)
            assert "sig" in result
            assert "bak" in result
            assert "ovrl" in result
            assert "composite" in result
        finally:
            os.unlink(path)

    def test_composite_in_range(self):
        path = make_wav(noise_scale=0.0)
        try:
            result = score_audio(path)
            assert 0.0 <= result["composite"] <= 1.0
        finally:
            os.unlink(path)

    def test_cleaner_audio_scores_higher(self):
        """Higher SNR (less noise) should produce a higher composite score."""
        clean_path = make_wav(noise_scale=0.0)
        noisy_path = make_wav(noise_scale=0.5)
        try:
            clean_score = score_audio(clean_path)["composite"]
            noisy_score = score_audio(noisy_path)["composite"]
            assert clean_score > noisy_score, (
                f"Clean ({clean_score:.3f}) should beat noisy ({noisy_score:.3f})"
            )
        finally:
            os.unlink(clean_path)
            os.unlink(noisy_path)

    def test_individual_scores_in_range(self):
        path = make_wav(noise_scale=0.05)
        try:
            result = score_audio(path)
            for key in ("sig", "bak", "ovrl"):
                assert 0.0 <= result[key] <= 1.0, f"{key} out of range: {result[key]}"
        finally:
            os.unlink(path)
```

### Step 2.2 — Run tests, expect failures

```bash
cd C:/Projects/AudioEnhanceMCP
pytest tests/test_score.py -v
```

Expected: all tests fail with `ModuleNotFoundError: No module named 'score'`

### Step 2.3 — Implement `score.py`

File: `C:/Projects/AudioEnhanceMCP/score.py`

```python
"""
score.py — DNSMOS-based composite audio quality scoring.

Composite formula:
  composite = 0.40 * norm(SIG) + 0.35 * norm(BAK) + 0.25 * norm(OVRL)
  where norm(x) = (x - 1) / 4  (maps [1,5] -> [0,1])
"""

import numpy as np
import soundfile as sf
import librosa
from speechmos import dnsmos


def load_audio(path: str) -> tuple[np.ndarray, int]:
    """Load an audio file and return (mono_float32_array, sample_rate).

    Stereo files are averaged to mono.
    """
    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    # Convert to mono by averaging channels
    if audio.shape[1] > 1:
        audio = audio.mean(axis=1)
    else:
        audio = audio[:, 0]
    return audio, sr


def resample_to_16k(audio: np.ndarray, sr: int) -> np.ndarray:
    """Resample audio to 16 kHz for DNSMOS scoring.

    Returns float32 array at 16000 Hz.
    """
    if sr == 16000:
        return audio.astype(np.float32)
    resampled = librosa.resample(audio.astype(np.float32), orig_sr=sr, target_sr=16000)
    return resampled.astype(np.float32)


def _normalize_mos(value: float) -> float:
    """Map a MOS score from [1, 5] to [0, 1]."""
    return max(0.0, min(1.0, (value - 1.0) / 4.0))


def score_audio(path: str) -> dict:
    """Score an audio file using DNSMOS.

    Returns:
        {
            "sig": float,        # normalized [0,1] speech signal quality
            "bak": float,        # normalized [0,1] background noise suppression
            "ovrl": float,       # normalized [0,1] overall quality
            "composite": float,  # weighted composite (SIG*0.40 + BAK*0.35 + OVRL*0.25)
        }
    """
    audio, sr = load_audio(path)
    audio_16k = resample_to_16k(audio, sr)

    result = dnsmos.run(audio_16k, sr=16000)

    sig = _normalize_mos(result["sig_mos"])
    bak = _normalize_mos(result["bak_mos"])
    ovrl = _normalize_mos(result["ovrl_mos"])

    composite = 0.40 * sig + 0.35 * bak + 0.25 * ovrl

    return {
        "sig": round(sig, 4),
        "bak": round(bak, 4),
        "ovrl": round(ovrl, 4),
        "composite": round(composite, 4),
    }
```

### Step 2.4 — Run tests, expect pass

```bash
cd C:/Projects/AudioEnhanceMCP
pytest tests/test_score.py -v
```

Expected output:
```
tests/test_score.py::TestLoadAudio::test_returns_array_and_sr PASSED
tests/test_score.py::TestLoadAudio::test_stereo_converted_to_mono PASSED
tests/test_score.py::TestResampleTo16k::test_resamples_correctly PASSED
tests/test_score.py::TestResampleTo16k::test_already_16k_unchanged PASSED
tests/test_score.py::TestScoreAudio::test_returns_expected_keys PASSED
tests/test_score.py::TestScoreAudio::test_composite_in_range PASSED
tests/test_score.py::TestScoreAudio::test_cleaner_audio_scores_higher PASSED
tests/test_score.py::TestScoreAudio::test_individual_scores_in_range PASSED
8 passed in Xs
```

If `test_cleaner_audio_scores_higher` is flaky (DNSMOS is not always sensitive to pure sine vs. sine+noise), regenerate with longer audio (5s) or a larger noise_scale (0.8).

### Step 2.5 — Commit

```bash
cd C:/Projects/AudioEnhanceMCP
git add score.py tests/test_score.py
git commit -m "Add scoring module with DNSMOS composite scorer"
```

---

## Task 3: Resemble Transform (`transforms/resemble.py`)

**Goal:** Wrap Resemble Enhance denoise and enhance APIs. Both functions load audio, run inference, save output, score the result, and return `{"output_path": str, "composite_score": float}`.

**sys.path note:** `C:/Projects/resemble` is injected into `sys.path` at the top of the module so Python can find the `resemble_enhance` package without installing it.

### Step 3.1 — Write tests first

File: `C:/Projects/AudioEnhanceMCP/tests/test_resemble.py`

```python
"""
Tests for transforms/resemble.py.

Marked @pytest.mark.slow because they load Resemble model weights (~100MB+).
Run with: pytest tests/test_resemble.py -v -m slow
Skip with: pytest tests/ -v -m "not slow"
"""

import os
import tempfile
import pytest
import soundfile as sf
import numpy as np

pytestmark = pytest.mark.slow

# Real audio fixture — first 3 seconds of a known file
REAL_WAV = "C:/Projects/DavinciMCP/AudioFiles/GRRM cleanvoice.wav"
CLIP_DURATION = 3  # seconds


@pytest.fixture(scope="module")
def short_wav(tmp_path_factory):
    """Extract the first 3 seconds of REAL_WAV into a temp file."""
    import soundfile as sf
    audio, sr = sf.read(REAL_WAV, dtype="float32", always_2d=True)
    clip = audio[: sr * CLIP_DURATION]
    out_dir = tmp_path_factory.mktemp("resemble_inputs")
    path = str(out_dir / "clip.wav")
    sf.write(path, clip, sr)
    return path


class TestDenoise:
    def test_output_file_created(self, short_wav, tmp_path):
        from transforms.resemble import denoise
        out = str(tmp_path / "denoised.wav")
        result = denoise(short_wav, out)
        assert os.path.exists(out), "Output file not created"
        assert result["output_path"] == out

    def test_returns_composite_score(self, short_wav, tmp_path):
        from transforms.resemble import denoise
        out = str(tmp_path / "denoised2.wav")
        result = denoise(short_wav, out)
        assert "composite_score" in result
        assert 0.0 <= result["composite_score"] <= 1.0

    def test_output_is_valid_wav(self, short_wav, tmp_path):
        from transforms.resemble import denoise
        out = str(tmp_path / "denoised3.wav")
        denoise(short_wav, out)
        audio, sr = sf.read(out)
        assert len(audio) > 0
        assert sr > 0


class TestEnhance:
    def test_output_file_created(self, short_wav, tmp_path):
        from transforms.resemble import enhance
        out = str(tmp_path / "enhanced.wav")
        result = enhance(short_wav, out)
        assert os.path.exists(out)
        assert result["output_path"] == out

    def test_returns_composite_score(self, short_wav, tmp_path):
        from transforms.resemble import enhance
        out = str(tmp_path / "enhanced2.wav")
        result = enhance(short_wav, out)
        assert "composite_score" in result
        assert 0.0 <= result["composite_score"] <= 1.0

    def test_lambd_tau_accepted(self, short_wav, tmp_path):
        from transforms.resemble import enhance
        out = str(tmp_path / "enhanced_custom.wav")
        # Should not raise
        result = enhance(short_wav, out, lambd=0.3, tau=0.7)
        assert os.path.exists(out)

    def test_output_is_valid_wav(self, short_wav, tmp_path):
        from transforms.resemble import enhance
        out = str(tmp_path / "enhanced3.wav")
        enhance(short_wav, out)
        audio, sr = sf.read(out)
        assert len(audio) > 0
```

### Step 3.2 — Run tests, expect failures

```bash
cd C:/Projects/AudioEnhanceMCP
pytest tests/test_resemble.py -v -m slow
```

Expected: `ImportError` or `ModuleNotFoundError: No module named 'transforms.resemble'`

### Step 3.3 — Implement `transforms/resemble.py`

File: `C:/Projects/AudioEnhanceMCP/transforms/resemble.py`

```python
"""
transforms/resemble.py — Wrappers for Resemble Enhance denoise and enhance.

Resemble Enhance is loaded from a local clone via sys.path injection.
CUDA is used if available, otherwise CPU (slower but functional).
"""

import sys
import os
import numpy as np
import soundfile as sf

# Inject local Resemble Enhance clone into Python path.
# The clone lives at C:/Projects/resemble and contains the resemble_enhance package.
_RESEMBLE_PATH = "C:/Projects/resemble"
if _RESEMBLE_PATH not in sys.path:
    sys.path.insert(0, _RESEMBLE_PATH)

import torch

# Import scoring after path injection (score.py is in the project root)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from score import load_audio, score_audio


def _get_device() -> str:
    """Return 'cuda' if a CUDA GPU is available, else 'cpu'."""
    return "cuda" if torch.cuda.is_available() else "cpu"


def denoise(input_path: str, output_path: str) -> dict:
    """Run Resemble Enhance in denoise-only mode.

    Loads audio from input_path, runs denoiser inference, saves result to
    output_path, then scores the output.

    Args:
        input_path: Path to source WAV file.
        output_path: Destination path for denoised WAV.

    Returns:
        {"output_path": str, "composite_score": float}
    """
    from resemble_enhance.denoiser.inference import denoise as _denoise

    audio, sr = load_audio(input_path)
    device = _get_device()

    audio_out, sr_out = _denoise(
        dwav=audio,
        sr=sr,
        run_dir=None,
        device=device,
    )

    # Ensure float32 for soundfile compatibility
    audio_out = np.array(audio_out, dtype=np.float32)
    sf.write(output_path, audio_out, sr_out)

    scores = score_audio(output_path)
    return {
        "output_path": output_path,
        "composite_score": scores["composite"],
    }


def enhance(
    input_path: str,
    output_path: str,
    lambd: float = 0.5,
    tau: float = 0.5,
) -> dict:
    """Run Resemble Enhance in full enhance mode (denoise + super-resolution).

    Args:
        input_path: Path to source WAV file.
        output_path: Destination path for enhanced WAV.
        lambd: Enhancement strength (0.0 = subtle, 1.0 = aggressive). Default 0.5.
        tau: CFM prior temperature. Lower = more faithful, higher = more creative.
             Default 0.5.

    Returns:
        {"output_path": str, "composite_score": float}
    """
    from resemble_enhance.enhancer.inference import enhance as _enhance

    audio, sr = load_audio(input_path)
    device = _get_device()

    audio_out, sr_out = _enhance(
        dwav=audio,
        sr=sr,
        device=device,
        nfe=32,
        solver="midpoint",
        lambd=lambd,
        tau=tau,
    )

    audio_out = np.array(audio_out, dtype=np.float32)
    sf.write(output_path, audio_out, sr_out)

    scores = score_audio(output_path)
    return {
        "output_path": output_path,
        "composite_score": scores["composite"],
    }
```

### Step 3.4 — Run tests, expect pass

```bash
cd C:/Projects/AudioEnhanceMCP
pytest tests/test_resemble.py -v -m slow
```

Expected output (may take 30–120 seconds due to model loading):
```
tests/test_resemble.py::TestDenoise::test_output_file_created PASSED
tests/test_resemble.py::TestDenoise::test_returns_composite_score PASSED
tests/test_resemble.py::TestDenoise::test_output_is_valid_wav PASSED
tests/test_resemble.py::TestEnhance::test_output_file_created PASSED
tests/test_resemble.py::TestEnhance::test_returns_composite_score PASSED
tests/test_resemble.py::TestEnhance::test_lambd_tau_accepted PASSED
tests/test_resemble.py::TestEnhance::test_output_is_valid_wav PASSED
7 passed in Xs
```

### Step 3.5 — Commit

```bash
cd C:/Projects/AudioEnhanceMCP
git add transforms/resemble.py tests/test_resemble.py
git commit -m "Add Resemble Enhance denoise and enhance transforms"
```

---

## Task 4: Loudness Transform (`transforms/loudness.py`)

**Goal:** Normalize integrated LUFS loudness using `pyloudnorm`. Measure current loudness, compute the required gain, apply, clip to [-1, 1], save.

### Step 4.1 — Write tests first

File: `C:/Projects/AudioEnhanceMCP/tests/test_loudness.py`

```python
import numpy as np
import soundfile as sf
import tempfile
import os
import pytest
from transforms.loudness import normalize_loudness


def make_wav_at_lufs(target_lufs: float, duration: float = 3.0, sr: int = 44100) -> str:
    """Generate a sine wave, normalize it to a known LUFS, save to temp WAV."""
    import pyloudnorm as pyln

    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    audio = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float64)

    meter = pyln.Meter(sr)
    loudness = meter.integrated_loudness(audio)
    if loudness > -70:  # avoid -inf for silence
        gain = 10 ** ((target_lufs - loudness) / 20)
        audio = audio * gain
    audio = np.clip(audio, -1.0, 1.0).astype(np.float32)

    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    sf.write(path, audio, sr)
    return path


class TestNormalizeLoudness:
    def test_output_file_created(self, tmp_path):
        src = make_wav_at_lufs(-24.0)
        out = str(tmp_path / "normalized.wav")
        try:
            result = normalize_loudness(src, out)
            assert os.path.exists(out)
            assert result["output_path"] == out
        finally:
            os.unlink(src)

    def test_returns_composite_score(self, tmp_path):
        src = make_wav_at_lufs(-24.0)
        out = str(tmp_path / "normalized2.wav")
        try:
            result = normalize_loudness(src, out)
            assert "composite_score" in result
            assert 0.0 <= result["composite_score"] <= 1.0
        finally:
            os.unlink(src)

    def test_output_within_half_lufs_of_target(self, tmp_path):
        """Output loudness must be within 0.5 LUFS of the target."""
        import pyloudnorm as pyln

        src = make_wav_at_lufs(-24.0)
        out = str(tmp_path / "normalized3.wav")
        target = -16.0
        try:
            normalize_loudness(src, out, target_lufs=target)
            audio, sr = sf.read(out, dtype="float64")
            meter = pyln.Meter(sr)
            measured = meter.integrated_loudness(audio)
            assert abs(measured - target) < 0.5, (
                f"Measured {measured:.2f} LUFS, expected {target:.2f} LUFS"
            )
        finally:
            os.unlink(src)

    def test_custom_target_lufs(self, tmp_path):
        """Test that a custom target LUFS (-23.0) is honored."""
        import pyloudnorm as pyln

        src = make_wav_at_lufs(-10.0)
        out = str(tmp_path / "normalized4.wav")
        target = -23.0
        try:
            normalize_loudness(src, out, target_lufs=target)
            audio, sr = sf.read(out, dtype="float64")
            meter = pyln.Meter(sr)
            measured = meter.integrated_loudness(audio)
            assert abs(measured - target) < 0.5
        finally:
            os.unlink(src)

    def test_original_file_not_modified(self, tmp_path):
        src = make_wav_at_lufs(-24.0)
        original_data, _ = sf.read(src)
        out = str(tmp_path / "normalized5.wav")
        try:
            normalize_loudness(src, out)
            after_data, _ = sf.read(src)
            np.testing.assert_array_equal(original_data, after_data)
        finally:
            os.unlink(src)
```

### Step 4.2 — Run tests, expect failures

```bash
cd C:/Projects/AudioEnhanceMCP
pytest tests/test_loudness.py -v
```

Expected: `ModuleNotFoundError: No module named 'transforms.loudness'`

### Step 4.3 — Implement `transforms/loudness.py`

File: `C:/Projects/AudioEnhanceMCP/transforms/loudness.py`

```python
"""
transforms/loudness.py — LUFS loudness normalization via pyloudnorm.

Measures integrated loudness of the input, computes the linear gain
required to hit the target, applies it, clips to [-1, 1], and saves.
"""

import os
import sys
import numpy as np
import soundfile as sf
import pyloudnorm as pyln

# Ensure score module is importable from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from score import score_audio


def normalize_loudness(
    input_path: str,
    output_path: str,
    target_lufs: float = -16.0,
) -> dict:
    """Normalize an audio file to the target integrated loudness.

    Args:
        input_path:   Path to source WAV file.
        output_path:  Destination path for loudness-normalized WAV.
        target_lufs:  Target integrated loudness in LUFS. Default -16.0
                      (standard for dialogue/voiceover).

    Returns:
        {"output_path": str, "composite_score": float}

    Notes:
        - If the measured loudness is -inf (silence or near-silence),
          the file is copied as-is with no gain applied.
        - Output is clipped to [-1.0, 1.0] to prevent digital clipping.
    """
    audio, sr = sf.read(input_path, dtype="float64", always_2d=True)

    # Convert stereo to mono for measurement, but keep original channels for output
    if audio.shape[1] == 1:
        mono = audio[:, 0]
    else:
        mono = audio.mean(axis=1)

    meter = pyln.Meter(sr)
    current_loudness = meter.integrated_loudness(mono)

    if current_loudness == float("-inf") or current_loudness < -70.0:
        # Silent or near-silent file — write as-is
        sf.write(output_path, audio.squeeze(), sr)
    else:
        gain_db = target_lufs - current_loudness
        gain_linear = 10.0 ** (gain_db / 20.0)
        normalized = np.clip(audio * gain_linear, -1.0, 1.0)
        sf.write(output_path, normalized.squeeze(), sr)

    scores = score_audio(output_path)
    return {
        "output_path": output_path,
        "composite_score": scores["composite"],
    }
```

### Step 4.4 — Run tests, expect pass

```bash
cd C:/Projects/AudioEnhanceMCP
pytest tests/test_loudness.py -v
```

Expected output:
```
tests/test_loudness.py::TestNormalizeLoudness::test_output_file_created PASSED
tests/test_loudness.py::TestNormalizeLoudness::test_returns_composite_score PASSED
tests/test_loudness.py::TestNormalizeLoudness::test_output_within_half_lufs_of_target PASSED
tests/test_loudness.py::TestNormalizeLoudness::test_custom_target_lufs PASSED
tests/test_loudness.py::TestNormalizeLoudness::test_original_file_not_modified PASSED
5 passed in Xs
```

### Step 4.5 — Commit

```bash
cd C:/Projects/AudioEnhanceMCP
git add transforms/loudness.py tests/test_loudness.py
git commit -m "Add loudness normalization transform"
```

---

## Task 5: Noise Reduce Transform (`transforms/noise_reduce.py`)

**Goal:** Wrap `noisereduce` stationary noise reduction. Load audio, run `noisereduce.reduce_noise()`, save, score, return result.

### Step 5.1 — Write tests first

File: `C:/Projects/AudioEnhanceMCP/tests/test_noise_reduce.py`

```python
import numpy as np
import soundfile as sf
import tempfile
import os
import pytest
from transforms.noise_reduce import reduce_noise


def make_noisy_wav(noise_scale=0.3, duration=2.0, sr=22050) -> str:
    """Generate a sine wave with white noise added."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    sine = 0.5 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    noise = (np.random.randn(len(t)) * noise_scale).astype(np.float32)
    mixed = np.clip(sine + noise, -1.0, 1.0)
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    sf.write(path, mixed, sr)
    return path


class TestReduceNoise:
    def test_output_file_created(self, tmp_path):
        src = make_noisy_wav()
        out = str(tmp_path / "reduced.wav")
        try:
            result = reduce_noise(src, out)
            assert os.path.exists(out)
            assert result["output_path"] == out
        finally:
            os.unlink(src)

    def test_returns_composite_score(self, tmp_path):
        src = make_noisy_wav()
        out = str(tmp_path / "reduced2.wav")
        try:
            result = reduce_noise(src, out)
            assert "composite_score" in result
            assert 0.0 <= result["composite_score"] <= 1.0
        finally:
            os.unlink(src)

    def test_output_scores_higher_than_input(self, tmp_path):
        """Noise-reduced output should score higher than the noisy input."""
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from score import score_audio

        src = make_noisy_wav(noise_scale=0.4, duration=3.0)
        out = str(tmp_path / "reduced3.wav")
        try:
            input_score = score_audio(src)["composite"]
            result = reduce_noise(src, out)
            output_score = result["composite_score"]
            assert output_score >= input_score, (
                f"Output score {output_score:.3f} should be >= input score {input_score:.3f}"
            )
        finally:
            os.unlink(src)

    def test_output_is_valid_wav(self, tmp_path):
        src = make_noisy_wav()
        out = str(tmp_path / "reduced4.wav")
        try:
            reduce_noise(src, out)
            audio, sr = sf.read(out)
            assert len(audio) > 0
            assert sr > 0
        finally:
            os.unlink(src)

    def test_original_not_modified(self, tmp_path):
        src = make_noisy_wav()
        original, _ = sf.read(src)
        out = str(tmp_path / "reduced5.wav")
        try:
            reduce_noise(src, out)
            after, _ = sf.read(src)
            np.testing.assert_array_equal(original, after)
        finally:
            os.unlink(src)
```

### Step 5.2 — Run tests, expect failures

```bash
cd C:/Projects/AudioEnhanceMCP
pytest tests/test_noise_reduce.py -v
```

Expected: `ModuleNotFoundError: No module named 'transforms.noise_reduce'`

### Step 5.3 — Implement `transforms/noise_reduce.py`

File: `C:/Projects/AudioEnhanceMCP/transforms/noise_reduce.py`

```python
"""
transforms/noise_reduce.py — Stationary noise reduction via noisereduce.

Uses noisereduce's stationary algorithm, which estimates a noise profile
from the entire signal and attenuates frequencies that match that profile.
Best suited for consistent background noise (HVAC, room tone, camera hiss).
"""

import os
import sys
import numpy as np
import soundfile as sf
import noisereduce as nr

# Ensure score module is importable from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from score import score_audio


def reduce_noise(input_path: str, output_path: str) -> dict:
    """Apply stationary spectral noise reduction to an audio file.

    Args:
        input_path:  Path to source WAV file.
        output_path: Destination path for noise-reduced WAV.

    Returns:
        {"output_path": str, "composite_score": float}
    """
    audio, sr = sf.read(input_path, dtype="float32", always_2d=True)

    # noisereduce operates on 1D or 2D arrays
    if audio.shape[1] == 1:
        audio_1d = audio[:, 0]
        reduced = nr.reduce_noise(y=audio_1d, sr=sr, stationary=True)
        sf.write(output_path, reduced, sr)
    else:
        # Process each channel independently
        channels = []
        for ch in range(audio.shape[1]):
            reduced_ch = nr.reduce_noise(y=audio[:, ch], sr=sr, stationary=True)
            channels.append(reduced_ch)
        reduced_stereo = np.stack(channels, axis=1)
        sf.write(output_path, reduced_stereo, sr)

    scores = score_audio(output_path)
    return {
        "output_path": output_path,
        "composite_score": scores["composite"],
    }
```

### Step 5.4 — Run tests, expect pass

```bash
cd C:/Projects/AudioEnhanceMCP
pytest tests/test_noise_reduce.py -v
```

Expected output:
```
tests/test_noise_reduce.py::TestReduceNoise::test_output_file_created PASSED
tests/test_noise_reduce.py::TestReduceNoise::test_returns_composite_score PASSED
tests/test_noise_reduce.py::TestReduceNoise::test_output_scores_higher_than_input PASSED
tests/test_noise_reduce.py::TestReduceNoise::test_output_is_valid_wav PASSED
tests/test_noise_reduce.py::TestReduceNoise::test_original_not_modified PASSED
5 passed in Xs
```

Note: `test_output_scores_higher_than_input` uses `>=` (not `>`) because DNSMOS BAK is not always strictly monotone. If this is still flaky, increase `noise_scale` to 0.6 or duration to 5.0.

### Step 5.5 — Commit

```bash
cd C:/Projects/AudioEnhanceMCP
git add transforms/noise_reduce.py tests/test_noise_reduce.py
git commit -m "Add spectral noise reduction transform"
```

---

## Task 6: Optimizer (`optimizer.py`)

**Goal:** Implement `auto_enhance()`. Runs a greedy recipe search over 7 preset recipes in Round 1, then generates parameter variations around the winner in subsequent rounds. Always applies transforms to the original file. Stops on plateau (<0.02 gain), score threshold (≥0.90), or max_rounds.

### Step 6.1 — Write tests first

File: `C:/Projects/AudioEnhanceMCP/tests/test_optimizer.py`

```python
"""
Tests for optimizer.py.

All transform functions are mocked — no model inference is run.
This tests the optimizer's control flow and stopping logic only.
"""

import os
import tempfile
import pytest
import soundfile as sf
import numpy as np
from unittest.mock import patch, MagicMock


def make_wav(path: str, duration: float = 1.0, sr: int = 22050):
    """Write a minimal WAV file at path."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    audio = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(path, audio, sr)


# ---- Helper: build a mock transform that returns a fixed score ----

def mock_transform(score: float, out_path_arg: str = "output_path"):
    """Return a mock callable that copies input to output and returns a fixed score."""
    def _fn(input_path, output_path, **kwargs):
        import shutil
        shutil.copy(input_path, output_path)
        return {"output_path": output_path, "composite_score": score}
    return _fn


# ---- Patch targets ----
# All transform functions called inside optimizer are patched via their
# fully-qualified names as imported in optimizer.py.

PATCH_SCORE = "optimizer.score_audio"
PATCH_DENOISE = "optimizer.denoise"
PATCH_ENHANCE = "optimizer.enhance"
PATCH_NORMALIZE = "optimizer.normalize_loudness"
PATCH_REDUCE = "optimizer.reduce_noise"


class TestAutoEnhanceReturnSchema:
    def test_returns_required_keys(self, tmp_path):
        """Result must contain all 6 required keys."""
        src = str(tmp_path / "input.wav")
        out = str(tmp_path / "output.wav")
        make_wav(src)

        with patch(PATCH_SCORE, return_value={"composite": 0.60}), \
             patch(PATCH_DENOISE, side_effect=mock_transform(0.65)), \
             patch(PATCH_ENHANCE, side_effect=mock_transform(0.70)), \
             patch(PATCH_NORMALIZE, side_effect=mock_transform(0.68)), \
             patch(PATCH_REDUCE, side_effect=mock_transform(0.64)):

            from optimizer import auto_enhance
            result = auto_enhance(src, out, max_rounds=1)

        required = {"output_path", "baseline_score", "final_score",
                    "improvement", "stop_reason", "log"}
        assert required.issubset(result.keys())

    def test_output_path_matches(self, tmp_path):
        src = str(tmp_path / "input.wav")
        out = str(tmp_path / "output.wav")
        make_wav(src)

        with patch(PATCH_SCORE, return_value={"composite": 0.60}), \
             patch(PATCH_DENOISE, side_effect=mock_transform(0.65)), \
             patch(PATCH_ENHANCE, side_effect=mock_transform(0.70)), \
             patch(PATCH_NORMALIZE, side_effect=mock_transform(0.68)), \
             patch(PATCH_REDUCE, side_effect=mock_transform(0.64)):

            from optimizer import auto_enhance
            result = auto_enhance(src, out, max_rounds=1)

        assert result["output_path"] == out


class TestStopConditions:
    def test_stops_on_threshold(self, tmp_path):
        """If best score >= 0.90, stop_reason should be 'threshold'."""
        src = str(tmp_path / "input.wav")
        out = str(tmp_path / "output.wav")
        make_wav(src)

        with patch(PATCH_SCORE, return_value={"composite": 0.60}), \
             patch(PATCH_DENOISE, side_effect=mock_transform(0.92)), \
             patch(PATCH_ENHANCE, side_effect=mock_transform(0.85)), \
             patch(PATCH_NORMALIZE, side_effect=mock_transform(0.75)), \
             patch(PATCH_REDUCE, side_effect=mock_transform(0.70)):

            from optimizer import auto_enhance
            result = auto_enhance(src, out, max_rounds=5)

        assert result["stop_reason"] == "threshold"
        assert result["final_score"] >= 0.90

    def test_stops_on_plateau(self, tmp_path):
        """If improvement between rounds < 0.02, stop_reason should be 'plateau'."""
        src = str(tmp_path / "input.wav")
        out = str(tmp_path / "output.wav")
        make_wav(src)

        # Round 1: best score = 0.70. Round 2 refinements return 0.71 (delta = 0.01 < 0.02).
        call_count = [0]
        def mock_enhance_plateau(input_path, output_path, **kwargs):
            import shutil
            shutil.copy(input_path, output_path)
            call_count[0] += 1
            # First 7 calls are round 1 recipes; give one a score of 0.70
            if call_count[0] == 3:
                return {"output_path": output_path, "composite_score": 0.70}
            # Round 2 refinements: return 0.71
            return {"output_path": output_path, "composite_score": 0.71}

        with patch(PATCH_SCORE, return_value={"composite": 0.60}), \
             patch(PATCH_DENOISE, side_effect=mock_transform(0.62)), \
             patch(PATCH_ENHANCE, side_effect=mock_enhance_plateau), \
             patch(PATCH_NORMALIZE, side_effect=mock_transform(0.63)), \
             patch(PATCH_REDUCE, side_effect=mock_transform(0.61)):

            from optimizer import auto_enhance
            result = auto_enhance(src, out, max_rounds=5)

        assert result["stop_reason"] == "plateau"

    def test_stops_on_max_rounds(self, tmp_path):
        """If max_rounds is exhausted without plateau or threshold, stop_reason is 'max_rounds'."""
        src = str(tmp_path / "input.wav")
        out = str(tmp_path / "output.wav")
        make_wav(src)

        # Each successive call returns 0.05 more — never plateaus, never hits 0.90
        call_count = [0]
        scores = [0.61, 0.63, 0.64, 0.62, 0.60,   # round 1 recipes
                  0.66, 0.67, 0.68,                  # round 2 refinements
                  0.70, 0.72, 0.74,                  # round 3
                  0.76, 0.78, 0.80,                  # round 4
                  0.82, 0.84, 0.86]                  # round 5

        def mock_enhance_improving(input_path, output_path, **kwargs):
            import shutil
            shutil.copy(input_path, output_path)
            idx = call_count[0] % len(scores)
            call_count[0] += 1
            return {"output_path": output_path, "composite_score": scores[idx]}

        with patch(PATCH_SCORE, return_value={"composite": 0.60}), \
             patch(PATCH_DENOISE, side_effect=mock_transform(0.61)), \
             patch(PATCH_ENHANCE, side_effect=mock_enhance_improving), \
             patch(PATCH_NORMALIZE, side_effect=mock_transform(0.61)), \
             patch(PATCH_REDUCE, side_effect=mock_transform(0.60)):

            from optimizer import auto_enhance
            result = auto_enhance(src, out, max_rounds=3)

        assert result["stop_reason"] == "max_rounds"

    def test_improvement_computed_correctly(self, tmp_path):
        src = str(tmp_path / "input.wav")
        out = str(tmp_path / "output.wav")
        make_wav(src)

        with patch(PATCH_SCORE, return_value={"composite": 0.50}), \
             patch(PATCH_DENOISE, side_effect=mock_transform(0.75)), \
             patch(PATCH_ENHANCE, side_effect=mock_transform(0.70)), \
             patch(PATCH_NORMALIZE, side_effect=mock_transform(0.68)), \
             patch(PATCH_REDUCE, side_effect=mock_transform(0.65)):

            from optimizer import auto_enhance
            result = auto_enhance(src, out, max_rounds=1)

        expected_improvement = round(result["final_score"] - result["baseline_score"], 4)
        assert abs(result["improvement"] - expected_improvement) < 0.001


class TestLog:
    def test_log_is_list(self, tmp_path):
        src = str(tmp_path / "input.wav")
        out = str(tmp_path / "output.wav")
        make_wav(src)

        with patch(PATCH_SCORE, return_value={"composite": 0.60}), \
             patch(PATCH_DENOISE, side_effect=mock_transform(0.65)), \
             patch(PATCH_ENHANCE, side_effect=mock_transform(0.70)), \
             patch(PATCH_NORMALIZE, side_effect=mock_transform(0.68)), \
             patch(PATCH_REDUCE, side_effect=mock_transform(0.64)):

            from optimizer import auto_enhance
            result = auto_enhance(src, out, max_rounds=1)

        assert isinstance(result["log"], list)
        assert len(result["log"]) >= 1

    def test_log_entries_have_required_keys(self, tmp_path):
        src = str(tmp_path / "input.wav")
        out = str(tmp_path / "output.wav")
        make_wav(src)

        with patch(PATCH_SCORE, return_value={"composite": 0.60}), \
             patch(PATCH_DENOISE, side_effect=mock_transform(0.65)), \
             patch(PATCH_ENHANCE, side_effect=mock_transform(0.70)), \
             patch(PATCH_NORMALIZE, side_effect=mock_transform(0.68)), \
             patch(PATCH_REDUCE, side_effect=mock_transform(0.64)):

            from optimizer import auto_enhance
            result = auto_enhance(src, out, max_rounds=2)

        for entry in result["log"]:
            assert "round" in entry
            assert "recipe" in entry
            assert "score" in entry
```

### Step 6.2 — Run tests, expect failures

```bash
cd C:/Projects/AudioEnhanceMCP
pytest tests/test_optimizer.py -v
```

Expected: `ModuleNotFoundError: No module named 'optimizer'`

### Step 6.3 — Implement `optimizer.py`

File: `C:/Projects/AudioEnhanceMCP/optimizer.py`

```python
"""
optimizer.py — Greedy auto-enhance loop with DNSMOS composite scoring.

Round 1: Evaluate all 7 preset recipes sequentially (to avoid GPU contention).
Round 2+: Generate parameter variations around the winning recipe's lambd/tau.
Always applies transforms to the original input file — no chaining between rounds.

Stopping conditions (first triggered wins):
  - plateau:    improvement between rounds < 0.02
  - threshold:  best composite score >= 0.90
  - max_rounds: max_rounds exhausted
"""

import os
import sys
import shutil
import tempfile

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from score import score_audio
from transforms.resemble import denoise, enhance
from transforms.loudness import normalize_loudness
from transforms.noise_reduce import reduce_noise

# Stopping thresholds
PLATEAU_DELTA = 0.02
SCORE_THRESHOLD = 0.90


def _run_recipe(recipe_name: str, input_path: str, work_dir: str) -> tuple[float, str]:
    """Execute a named recipe on input_path, return (score, output_path).

    Output is written to a temp file in work_dir. The caller is responsible
    for copying the winning output to the final destination.
    """
    out = os.path.join(work_dir, f"{recipe_name.replace(' ', '_').replace('+', '__')}.wav")

    if recipe_name == "denoise_only":
        result = denoise(input_path, out)

    elif recipe_name == "enhance_light":
        result = enhance(input_path, out, lambd=0.3, tau=0.5)

    elif recipe_name == "enhance_medium":
        result = enhance(input_path, out, lambd=0.5, tau=0.5)

    elif recipe_name == "enhance_strong":
        result = enhance(input_path, out, lambd=0.7, tau=0.5)

    elif recipe_name == "normalize_only":
        result = normalize_loudness(input_path, out, target_lufs=-16.0)

    elif recipe_name == "denoise+normalize":
        tmp = os.path.join(work_dir, "denoise_tmp.wav")
        denoise(input_path, tmp)
        result = normalize_loudness(tmp, out, target_lufs=-16.0)

    elif recipe_name == "enhance_medium+normalize":
        tmp = os.path.join(work_dir, "enhance_tmp.wav")
        enhance(input_path, tmp, lambd=0.5, tau=0.5)
        result = normalize_loudness(tmp, out, target_lufs=-16.0)

    else:
        raise ValueError(f"Unknown recipe: {recipe_name!r}")

    return result["composite_score"], out


def _round1_recipes() -> list[str]:
    return [
        "denoise_only",
        "enhance_light",
        "enhance_medium",
        "enhance_strong",
        "normalize_only",
        "denoise+normalize",
        "enhance_medium+normalize",
    ]


def _round2_plus_recipes(winner: str) -> list[tuple[str, dict]]:
    """Generate refinement recipes around the winning recipe.

    Returns a list of (recipe_label, kwargs) tuples for enhance() calls
    with varied lambd and tau. If the winner does not use enhance, generate
    enhance variations starting from medium parameters.
    """
    # Extract lambd from winner name if available
    if "enhance_light" in winner:
        base_lambd = 0.3
    elif "enhance_strong" in winner:
        base_lambd = 0.7
    elif "enhance_medium" in winner or "enhance" in winner:
        base_lambd = 0.5
    else:
        base_lambd = 0.5  # default starting point for non-enhance winners

    variations = []
    for lambd_delta in (-0.2, -0.1, 0.1, 0.2):
        lambd = round(max(0.0, min(1.0, base_lambd + lambd_delta)), 1)
        for tau in (0.3, 0.5, 0.7):
            label = f"enhance(lambd={lambd},tau={tau})"
            if "normalize" in winner:
                label += "+normalize"
            variations.append((label, {"lambd": lambd, "tau": tau, "normalize": "normalize" in winner}))

    return variations


def _run_refinement_recipe(label: str, kwargs: dict, input_path: str, work_dir: str) -> tuple[float, str]:
    """Run a Round 2+ refinement recipe."""
    safe_label = label.replace("=", "").replace(",", "_").replace("(", "").replace(")", "").replace("+", "__")
    out = os.path.join(work_dir, f"{safe_label}.wav")

    lambd = kwargs["lambd"]
    tau = kwargs["tau"]
    do_normalize = kwargs.get("normalize", False)

    if do_normalize:
        tmp = os.path.join(work_dir, f"enh_tmp_{safe_label}.wav")
        enhance(input_path, tmp, lambd=lambd, tau=tau)
        result = normalize_loudness(tmp, out, target_lufs=-16.0)
    else:
        result = enhance(input_path, out, lambd=lambd, tau=tau)

    return result["composite_score"], out


def auto_enhance(
    input_path: str,
    output_path: str,
    max_rounds: int = 5,
) -> dict:
    """Run greedy auto-enhance optimization on an audio file.

    Args:
        input_path:  Path to source WAV file. Never modified.
        output_path: Destination path for the best-found output.
        max_rounds:  Maximum number of optimization rounds. Default 5.

    Returns:
        {
            "output_path": str,
            "baseline_score": float,
            "final_score": float,
            "improvement": float,
            "stop_reason": str,   # "threshold" | "plateau" | "max_rounds"
            "log": list[dict],    # [{round, recipe, score}, ...]
        }
    """
    baseline_scores = score_audio(input_path)
    baseline = baseline_scores["composite"]

    log = []
    best_score = baseline
    best_output = None
    stop_reason = "max_rounds"
    prev_round_best = baseline

    with tempfile.TemporaryDirectory() as work_dir:

        for round_num in range(1, max_rounds + 1):

            round_best_score = -1.0
            round_best_path = None
            round_best_recipe = None

            if round_num == 1:
                # --- Round 1: sweep all preset recipes ---
                for recipe in _round1_recipes():
                    try:
                        score, path = _run_recipe(recipe, input_path, work_dir)
                    except Exception as e:
                        log.append({"round": round_num, "recipe": recipe, "score": None, "error": str(e)})
                        continue
                    log.append({"round": round_num, "recipe": recipe, "score": round(score, 4)})
                    if score > round_best_score:
                        round_best_score = score
                        round_best_path = path
                        round_best_recipe = recipe

            else:
                # --- Round 2+: refine around winner ---
                winner = round_best_recipe or "enhance_medium"
                for label, kwargs in _round2_plus_recipes(winner):
                    try:
                        score, path = _run_refinement_recipe(label, kwargs, input_path, work_dir)
                    except Exception as e:
                        log.append({"round": round_num, "recipe": label, "score": None, "error": str(e)})
                        continue
                    log.append({"round": round_num, "recipe": label, "score": round(score, 4)})
                    if score > round_best_score:
                        round_best_score = score
                        round_best_path = path
                        round_best_recipe = label

            # Update global best
            if round_best_score > best_score and round_best_path is not None:
                best_score = round_best_score
                best_output = round_best_path

            # --- Check stopping conditions ---
            if best_score >= SCORE_THRESHOLD:
                stop_reason = "threshold"
                break

            improvement_this_round = best_score - prev_round_best
            if round_num > 1 and improvement_this_round < PLATEAU_DELTA:
                stop_reason = "plateau"
                break

            prev_round_best = best_score

        # Copy best output to the caller-specified output_path
        if best_output is not None and os.path.exists(best_output):
            shutil.copy(best_output, output_path)
        else:
            # No improvement found — copy original
            shutil.copy(input_path, output_path)
            best_score = baseline

    improvement = round(best_score - baseline, 4)
    return {
        "output_path": output_path,
        "baseline_score": round(baseline, 4),
        "final_score": round(best_score, 4),
        "improvement": improvement,
        "stop_reason": stop_reason,
        "log": log,
    }
```

### Step 6.4 — Run tests, expect pass

```bash
cd C:/Projects/AudioEnhanceMCP
pytest tests/test_optimizer.py -v
```

Expected output:
```
tests/test_optimizer.py::TestAutoEnhanceReturnSchema::test_returns_required_keys PASSED
tests/test_optimizer.py::TestAutoEnhanceReturnSchema::test_output_path_matches PASSED
tests/test_optimizer.py::TestStopConditions::test_stops_on_threshold PASSED
tests/test_optimizer.py::TestStopConditions::test_stops_on_plateau PASSED
tests/test_optimizer.py::TestStopConditions::test_stops_on_max_rounds PASSED
tests/test_optimizer.py::TestStopConditions::test_improvement_computed_correctly PASSED
tests/test_optimizer.py::TestLog::test_log_is_list PASSED
tests/test_optimizer.py::TestLog::test_log_entries_have_required_keys PASSED
8 passed in Xs
```

If `test_stops_on_plateau` fails because the mock doesn't trigger exactly after round 2, adjust the plateau mock's score sequence so Round 1 best = 0.70 and all Round 2 variations return ≤ 0.71.

### Step 6.5 — Commit

```bash
cd C:/Projects/AudioEnhanceMCP
git add optimizer.py tests/test_optimizer.py
git commit -m "Add auto-enhance optimizer with greedy recipe search"
```

---

## Task 7: MCP Server (`server.py`)

**Goal:** Wire all 6 tools as `@mcp.tool()` functions. Every tool catches exceptions and returns `{"error": str}`. Integration tests call each tool with a real file and verify response shape.

### Step 7.1 — Write tests first

File: `C:/Projects/AudioEnhanceMCP/tests/test_server.py`

```python
"""
Integration tests for server.py.

These tests instantiate tools directly from the module — they do NOT start the
MCP server process. Each tool is called with real audio to verify the response
schema. Resemble-based tests are marked slow.
"""

import os
import sys
import pytest
import soundfile as sf
import numpy as np
import tempfile
from unittest.mock import patch


# Test audio fixture
REAL_WAV = "C:/Projects/DavinciMCP/AudioFiles/GRRM cleanvoice.wav"


@pytest.fixture(scope="module")
def short_wav(tmp_path_factory):
    """3-second clip of REAL_WAV written to a temp file."""
    audio, sr = sf.read(REAL_WAV, dtype="float32", always_2d=True)
    clip = audio[: sr * 3]
    out_dir = tmp_path_factory.mktemp("server_inputs")
    path = str(out_dir / "clip.wav")
    sf.write(path, clip, sr)
    return path


@pytest.fixture(scope="module")
def synth_wav(tmp_path_factory):
    """Synthetic sine+noise WAV for fast (non-slow) tests."""
    sr = 22050
    t = np.linspace(0, 2.0, int(sr * 2.0), endpoint=False)
    audio = (0.3 * np.sin(2 * np.pi * 440 * t) +
             0.1 * np.random.randn(len(t))).astype(np.float32)
    out_dir = tmp_path_factory.mktemp("server_synth")
    path = str(out_dir / "synth.wav")
    sf.write(path, audio, sr)
    return path


class TestScoreAudioTool:
    def test_returns_expected_keys(self, synth_wav):
        from server import score_audio_tool
        result = score_audio_tool(input_path=synth_wav)
        assert "sig" in result
        assert "bak" in result
        assert "ovrl" in result
        assert "composite" in result

    def test_error_on_missing_file(self):
        from server import score_audio_tool
        result = score_audio_tool(input_path="/nonexistent/file.wav")
        assert "error" in result


class TestNormalizeLoudnessTool:
    def test_returns_output_path_and_score(self, synth_wav, tmp_path):
        from server import normalize_loudness_tool
        out = str(tmp_path / "norm.wav")
        result = normalize_loudness_tool(input_path=synth_wav, output_path=out)
        assert "output_path" in result
        assert "composite_score" in result
        assert os.path.exists(out)

    def test_error_on_missing_file(self, tmp_path):
        from server import normalize_loudness_tool
        out = str(tmp_path / "norm_err.wav")
        result = normalize_loudness_tool(input_path="/nonexistent.wav", output_path=out)
        assert "error" in result


class TestReduceNoiseTool:
    def test_returns_output_path_and_score(self, synth_wav, tmp_path):
        from server import reduce_noise_tool
        out = str(tmp_path / "reduced.wav")
        result = reduce_noise_tool(input_path=synth_wav, output_path=out)
        assert "output_path" in result
        assert "composite_score" in result
        assert os.path.exists(out)

    def test_error_on_missing_file(self, tmp_path):
        from server import reduce_noise_tool
        out = str(tmp_path / "reduced_err.wav")
        result = reduce_noise_tool(input_path="/nonexistent.wav", output_path=out)
        assert "error" in result


@pytest.mark.slow
class TestDenoiseAudioTool:
    def test_returns_output_path_and_score(self, short_wav, tmp_path):
        from server import denoise_audio_tool
        out = str(tmp_path / "denoised.wav")
        result = denoise_audio_tool(input_path=short_wav, output_path=out)
        assert "output_path" in result
        assert "composite_score" in result
        assert os.path.exists(out)

    def test_error_on_missing_file(self, tmp_path):
        from server import denoise_audio_tool
        out = str(tmp_path / "denoised_err.wav")
        result = denoise_audio_tool(input_path="/nonexistent.wav", output_path=out)
        assert "error" in result


@pytest.mark.slow
class TestEnhanceAudioTool:
    def test_returns_output_path_and_score(self, short_wav, tmp_path):
        from server import enhance_audio_tool
        out = str(tmp_path / "enhanced.wav")
        result = enhance_audio_tool(input_path=short_wav, output_path=out)
        assert "output_path" in result
        assert "composite_score" in result

    def test_custom_lambd_tau(self, short_wav, tmp_path):
        from server import enhance_audio_tool
        out = str(tmp_path / "enhanced_custom.wav")
        result = enhance_audio_tool(input_path=short_wav, output_path=out, lambd=0.3, tau=0.7)
        assert "output_path" in result

    def test_error_on_missing_file(self, tmp_path):
        from server import enhance_audio_tool
        out = str(tmp_path / "enhanced_err.wav")
        result = enhance_audio_tool(input_path="/nonexistent.wav", output_path=out)
        assert "error" in result


@pytest.mark.slow
class TestAutoEnhanceTool:
    def test_returns_all_required_keys(self, short_wav, tmp_path):
        from server import auto_enhance_tool
        out = str(tmp_path / "auto.wav")
        result = auto_enhance_tool(input_path=short_wav, output_path=out, max_rounds=1)
        required = {"output_path", "baseline_score", "final_score",
                    "improvement", "stop_reason", "log"}
        assert required.issubset(result.keys())

    def test_error_on_missing_file(self, tmp_path):
        from server import auto_enhance_tool
        out = str(tmp_path / "auto_err.wav")
        result = auto_enhance_tool(input_path="/nonexistent.wav", output_path=out)
        assert "error" in result
```

### Step 7.2 — Run tests, expect failures

```bash
cd C:/Projects/AudioEnhanceMCP
pytest tests/test_server.py -v -m "not slow"
```

Expected: `ModuleNotFoundError: No module named 'server'`

### Step 7.3 — Implement `server.py`

File: `C:/Projects/AudioEnhanceMCP/server.py`

```python
"""
server.py — AudioEnhanceMCP FastMCP server.

Exposes 6 tools for audio quality enhancement:
  score_audio      — DNSMOS composite scoring
  denoise_audio    — Resemble denoiser
  enhance_audio    — Resemble full enhancer (tunable lambd/tau)
  normalize_loudness — LUFS loudness normalization
  reduce_noise     — Spectral noise reduction
  auto_enhance     — Greedy optimization loop

All tools catch exceptions and return {"error": str} rather than crashing.
"""

import sys
import os

# Ensure project root and Resemble clone are importable
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fastmcp import FastMCP
from score import score_audio
from transforms.resemble import denoise, enhance
from transforms.loudness import normalize_loudness
from transforms.noise_reduce import reduce_noise
from optimizer import auto_enhance

mcp = FastMCP("audio-enhance")


@mcp.tool()
def score_audio_tool(input_path: str) -> dict:
    """Score an audio file using DNSMOS and return a composite quality score.

    Args:
        input_path: Absolute path to a WAV file.

    Returns:
        {
            "sig": float,        # Speech signal quality [0,1]
            "bak": float,        # Background suppression [0,1]
            "ovrl": float,       # Overall quality [0,1]
            "composite": float,  # Weighted composite [0,1]
        }
        or {"error": str} on failure.
    """
    try:
        return score_audio(input_path)
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def denoise_audio_tool(input_path: str, output_path: str) -> dict:
    """Denoise an audio file using Resemble Enhance (denoise-only mode).

    Args:
        input_path:  Absolute path to source WAV.
        output_path: Absolute path for denoised output WAV.

    Returns:
        {"output_path": str, "composite_score": float}
        or {"error": str} on failure.
    """
    try:
        return denoise(input_path, output_path)
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def enhance_audio_tool(
    input_path: str,
    output_path: str,
    lambd: float = 0.5,
    tau: float = 0.5,
) -> dict:
    """Enhance an audio file using Resemble Enhance (full denoise + super-resolution).

    Args:
        input_path:  Absolute path to source WAV.
        output_path: Absolute path for enhanced output WAV.
        lambd:       Enhancement strength [0.0–1.0]. Default 0.5.
                     Lower = subtle, higher = aggressive processing.
        tau:         CFM prior temperature [0.0–1.0]. Default 0.5.
                     Lower = more faithful to original, higher = more generative.

    Returns:
        {"output_path": str, "composite_score": float}
        or {"error": str} on failure.
    """
    try:
        return enhance(input_path, output_path, lambd=lambd, tau=tau)
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def normalize_loudness_tool(
    input_path: str,
    output_path: str,
    target_lufs: float = -16.0,
) -> dict:
    """Normalize the loudness of an audio file to a target LUFS level.

    Args:
        input_path:   Absolute path to source WAV.
        output_path:  Absolute path for normalized output WAV.
        target_lufs:  Target integrated loudness in LUFS. Default -16.0
                      (standard for dialogue/voiceover).

    Returns:
        {"output_path": str, "composite_score": float}
        or {"error": str} on failure.
    """
    try:
        return normalize_loudness(input_path, output_path, target_lufs=target_lufs)
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def reduce_noise_tool(input_path: str, output_path: str) -> dict:
    """Apply stationary spectral noise reduction to an audio file.

    Best for consistent background noise: HVAC, room tone, camera hiss.

    Args:
        input_path:  Absolute path to source WAV.
        output_path: Absolute path for noise-reduced output WAV.

    Returns:
        {"output_path": str, "composite_score": float}
        or {"error": str} on failure.
    """
    try:
        return reduce_noise(input_path, output_path)
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def auto_enhance_tool(
    input_path: str,
    output_path: str,
    max_rounds: int = 5,
) -> dict:
    """Automatically optimize audio quality using a greedy enhancement loop.

    Tries 7 preset enhancement recipes in Round 1, then refines around the
    best parameters in subsequent rounds. Always processes the original file
    (no artifact accumulation). Stops when quality plateaus, hits the target
    threshold (0.90 composite), or exhausts max_rounds.

    Args:
        input_path:  Absolute path to source WAV.
        output_path: Absolute path for best-found output WAV.
        max_rounds:  Maximum optimization rounds. Default 5.

    Returns:
        {
            "output_path": str,
            "baseline_score": float,
            "final_score": float,
            "improvement": float,
            "stop_reason": str,   # "threshold" | "plateau" | "max_rounds"
            "log": list,          # [{round, recipe, score}, ...]
        }
        or {"error": str} on failure.
    """
    try:
        return auto_enhance(input_path, output_path, max_rounds=max_rounds)
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run()
```

### Step 7.4 — Run non-slow integration tests, expect pass

```bash
cd C:/Projects/AudioEnhanceMCP
pytest tests/test_server.py -v -m "not slow"
```

Expected output:
```
tests/test_server.py::TestScoreAudioTool::test_returns_expected_keys PASSED
tests/test_server.py::TestScoreAudioTool::test_error_on_missing_file PASSED
tests/test_server.py::TestNormalizeLoudnessTool::test_returns_output_path_and_score PASSED
tests/test_server.py::TestNormalizeLoudnessTool::test_error_on_missing_file PASSED
tests/test_server.py::TestReduceNoiseTool::test_returns_output_path_and_score PASSED
tests/test_server.py::TestReduceNoiseTool::test_error_on_missing_file PASSED
6 passed in Xs
```

### Step 7.5 — Commit

```bash
cd C:/Projects/AudioEnhanceMCP
git add server.py tests/test_server.py
git commit -m "Add FastMCP server with all 6 tools and integration tests"
```

---

## Task 8: README + Final Wiring

**Goal:** Write `README.md` with installation, MCP config, and tool reference. Run the full fast test suite. Final commit.

### Step 8.1 — Create `README.md`

File: `C:/Projects/AudioEnhanceMCP/README.md`

````markdown
# AudioEnhanceMCP

A standalone FastMCP server exposing 6 audio enhancement tools for dialogue and voiceover quality improvement. Driven by DNSMOS composite scoring with an auto-optimize loop.

## Requirements

- Python 3.10+
- CUDA GPU recommended (CPU works but is slower for Resemble operations)
- DaVinci Resolve not required — this is a standalone project

## Installation

### 1. Clone this repo

```bash
git clone <repo-url> C:/Projects/AudioEnhanceMCP
cd C:/Projects/AudioEnhanceMCP
```

### 2. Clone Resemble Enhance (local dependency)

```bash
git clone https://github.com/resemble-ai/resemble-enhance C:/Projects/resemble
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

> Note: `resemble-enhance` is loaded from `C:/Projects/resemble` via sys.path injection — do NOT pip-install it separately.

### 4. Verify installation

```bash
pytest tests/ -v -m "not slow"
```

All tests should pass. To also run slow Resemble tests:

```bash
pytest tests/ -v -m slow
```

## Add to Claude Desktop

Edit your Claude Desktop MCP config file (usually `~/.config/claude/claude_desktop_config.json` on macOS or `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "audio-enhance": {
      "command": "python",
      "args": ["C:/Projects/AudioEnhanceMCP/server.py"]
    }
  }
}
```

Restart Claude Desktop after saving.

## Tool Reference

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `score_audio_tool` | Score audio quality via DNSMOS | `input_path` |
| `denoise_audio_tool` | Resemble Enhance — denoise only | `input_path`, `output_path` |
| `enhance_audio_tool` | Resemble Enhance — full enhance | `input_path`, `output_path`, `lambd=0.5`, `tau=0.5` |
| `normalize_loudness_tool` | LUFS loudness normalization | `input_path`, `output_path`, `target_lufs=-16.0` |
| `reduce_noise_tool` | Spectral noise reduction | `input_path`, `output_path` |
| `auto_enhance_tool` | Auto-optimize loop (greedy search) | `input_path`, `output_path`, `max_rounds=5` |

### Composite Score Formula

```
composite = 0.40 * norm(SIG) + 0.35 * norm(BAK) + 0.25 * norm(OVRL)
norm(x) = (x - 1) / 4   # maps DNSMOS MOS [1,5] to [0,1]
```

Score ≥ 0.90 is considered high quality (auto_enhance stops early).

### `lambd` and `tau` Guidance

| Parameter | Low value | High value |
|-----------|-----------|------------|
| `lambd` (0–1) | Subtle enhancement, preserves original character | Aggressive, more artifacts possible |
| `tau` (0–1) | Faithful reconstruction | More generative / creative output |

Start with defaults (`lambd=0.5, tau=0.5`) and adjust based on source material.

## Example Usage (Claude prompt)

```
Score this file: C:/Projects/MyProject/AudioFiles/interview.wav

Then auto-enhance it and save the result to:
C:/Projects/MyProject/AudioFiles/interview_enhanced.wav
```

Claude will call `score_audio_tool` first, then `auto_enhance_tool`, and report the before/after composite scores and which recipe won.

## Project Structure

```
AudioEnhanceMCP/
├── server.py          # FastMCP server — entry point
├── score.py           # DNSMOS composite scoring
├── optimizer.py       # auto_enhance greedy loop
├── transforms/
│   ├── __init__.py
│   ├── resemble.py    # Resemble denoise + enhance
│   ├── loudness.py    # pyloudnorm LUFS normalization
│   └── noise_reduce.py # noisereduce spectral reduction
├── tests/
│   ├── test_score.py
│   ├── test_resemble.py   # marked slow
│   ├── test_loudness.py
│   ├── test_noise_reduce.py
│   ├── test_optimizer.py
│   └── test_server.py
├── requirements.txt
└── README.md
```
````

### Step 8.2 — Verify `server.py` has `__main__` block

Confirm `server.py` ends with:

```python
if __name__ == "__main__":
    mcp.run()
```

This is already included in the Task 7 implementation. No change needed.

### Step 8.3 — Run full fast test suite

```bash
cd C:/Projects/AudioEnhanceMCP
pytest tests/ -v -m "not slow"
```

Expected output (all passing, ~10–15 seconds):
```
tests/test_score.py::TestLoadAudio::test_returns_array_and_sr PASSED
tests/test_score.py::TestLoadAudio::test_stereo_converted_to_mono PASSED
tests/test_score.py::TestResampleTo16k::test_resamples_correctly PASSED
tests/test_score.py::TestResampleTo16k::test_already_16k_unchanged PASSED
tests/test_score.py::TestScoreAudio::test_returns_expected_keys PASSED
tests/test_score.py::TestScoreAudio::test_composite_in_range PASSED
tests/test_score.py::TestScoreAudio::test_cleaner_audio_scores_higher PASSED
tests/test_score.py::TestScoreAudio::test_individual_scores_in_range PASSED
tests/test_loudness.py::TestNormalizeLoudness::test_output_file_created PASSED
tests/test_loudness.py::TestNormalizeLoudness::test_returns_composite_score PASSED
tests/test_loudness.py::TestNormalizeLoudness::test_output_within_half_lufs_of_target PASSED
tests/test_loudness.py::TestNormalizeLoudness::test_custom_target_lufs PASSED
tests/test_loudness.py::TestNormalizeLoudness::test_original_file_not_modified PASSED
tests/test_noise_reduce.py::TestReduceNoise::test_output_file_created PASSED
tests/test_noise_reduce.py::TestReduceNoise::test_returns_composite_score PASSED
tests/test_noise_reduce.py::TestReduceNoise::test_output_scores_higher_than_input PASSED
tests/test_noise_reduce.py::TestReduceNoise::test_output_is_valid_wav PASSED
tests/test_noise_reduce.py::TestReduceNoise::test_original_not_modified PASSED
tests/test_optimizer.py::TestAutoEnhanceReturnSchema::test_returns_required_keys PASSED
tests/test_optimizer.py::TestAutoEnhanceReturnSchema::test_output_path_matches PASSED
tests/test_optimizer.py::TestStopConditions::test_stops_on_threshold PASSED
tests/test_optimizer.py::TestStopConditions::test_stops_on_plateau PASSED
tests/test_optimizer.py::TestStopConditions::test_stops_on_max_rounds PASSED
tests/test_optimizer.py::TestStopConditions::test_improvement_computed_correctly PASSED
tests/test_optimizer.py::TestLog::test_log_is_list PASSED
tests/test_optimizer.py::TestLog::test_log_entries_have_required_keys PASSED
tests/test_server.py::TestScoreAudioTool::test_returns_expected_keys PASSED
tests/test_server.py::TestScoreAudioTool::test_error_on_missing_file PASSED
tests/test_server.py::TestNormalizeLoudnessTool::test_returns_output_path_and_score PASSED
tests/test_server.py::TestNormalizeLoudnessTool::test_error_on_missing_file PASSED
tests/test_server.py::TestReduceNoiseTool::test_returns_output_path_and_score PASSED
tests/test_server.py::TestReduceNoiseTool::test_error_on_missing_file PASSED
32 passed in Xs
```

If any test fails at this stage, debug before proceeding to the final commit.

### Step 8.4 — Final commit

```bash
cd C:/Projects/AudioEnhanceMCP
git add README.md
git commit -m "Add README with installation, MCP config, and tool reference"
```

---

## Summary

| Task | Files Created | Tests | Commit |
|------|--------------|-------|--------|
| 1: Bootstrap | `requirements.txt`, `transforms/__init__.py`, `tests/__init__.py`, `.gitignore` | — | "Initial project scaffold" |
| 2: Scoring | `score.py`, `tests/test_score.py` | 8 fast | "Add scoring module with DNSMOS composite scorer" |
| 3: Resemble | `transforms/resemble.py`, `tests/test_resemble.py` | 7 slow | "Add Resemble Enhance denoise and enhance transforms" |
| 4: Loudness | `transforms/loudness.py`, `tests/test_loudness.py` | 5 fast | "Add loudness normalization transform" |
| 5: Noise Reduce | `transforms/noise_reduce.py`, `tests/test_noise_reduce.py` | 5 fast | "Add spectral noise reduction transform" |
| 6: Optimizer | `optimizer.py`, `tests/test_optimizer.py` | 8 fast (mocked) | "Add auto-enhance optimizer with greedy recipe search" |
| 7: Server | `server.py`, `tests/test_server.py` | 6 fast + 7 slow | "Add FastMCP server with all 6 tools and integration tests" |
| 8: README | `README.md` | — | "Add README with installation, MCP config, and tool reference" |

**Total: 8 commits, 32 fast tests, 14 slow tests**

Fast test suite command (use this for CI and iterative development):
```bash
pytest tests/ -v -m "not slow"
```

Full test suite (run once after initial setup to verify Resemble integration):
```bash
pytest tests/ -v
```
