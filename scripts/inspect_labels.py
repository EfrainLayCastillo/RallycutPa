# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy"]
# ///
"""Print candidate features per labeled interval to see what separates rally from dead time."""

import sys
from pathlib import Path

import numpy as np

from labels import load_labels


def features(sig, start, end):
    t = sig["t"]
    sel = (t >= start) & (t <= end)
    norm = lambda x: x / np.percentile(x, 95)
    near, far = norm(sig["near"]), norm(sig["far"])
    total = near + far
    hits = sig["hits"]
    return {
        "near": near[sel].mean(),
        "far": far[sel].mean(),
        "both": np.minimum(near, far)[sel].mean(),
        "jerk": np.abs(np.diff(total))[sel[1:]].mean(),
        "far_jerk": np.abs(np.diff(far))[sel[1:]].mean(),
        "hits/s": ((hits >= start) & (hits <= end)).sum() / (end - start),
        "audio": sig["audio_db"][sel].mean(),
    }


def main(work, *_):
    work = Path(work)
    sig = dict(np.load(work / "signals.npz"))
    rows = [(s, e, label, features(sig, s, e)) for s, e, label in load_labels(work.parent / "labels.csv")]
    keys = list(rows[0][3])
    print(f"{'interval':>13} {'label':>6} " + " ".join(f"{k:>8}" for k in keys))
    for s, e, label, f in sorted(rows, key=lambda r: r[2]):
        print(f"{s:6.0f}-{e:6.0f} {label:>6} " + " ".join(f"{f[k]:8.3f}" for k in keys))


if __name__ == "__main__":
    main(*sys.argv[1:])
