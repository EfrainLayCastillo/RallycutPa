import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

requires_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def make_signals(near, far, fps=5, hits=(), audio_db=None):
    near, far = np.asarray(near, float), np.asarray(far, float)
    n = len(near)
    return {
        "t": (np.arange(n) + 1) / fps,
        "near": near,
        "far": far,
        "shake": np.zeros(n),
        "board": np.zeros(n),
        "audio_db": np.zeros(n) if audio_db is None else np.asarray(audio_db, float),
        "hits": np.asarray(hits, float),
    }


def bursts(spans_s, total_s, fps=5, high=1.0, low=0.05):
    """Activity series that is `high` inside each (start, end) span in seconds and `low` elsewhere."""
    values = np.full(int(total_s * fps), low)
    for start, end in spans_s:
        values[int(start * fps): int(end * fps)] = high
    return values
