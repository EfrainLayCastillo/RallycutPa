# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy", "matplotlib"]
# ///
"""Grid-search segmentation params against labels.csv; prints the best combinations."""
import itertools
import json
import sys
from pathlib import Path

import numpy as np

from labels import label_metrics, load_labels
from segment import add_scores, build_segments, calibrate, top_segments

GRID = {
    "points_per_min": [1.2, 1.5, 1.7, 2.0],
    "off_ratio": [0.5, 0.6, 0.75],
    "smooth_s": [1.0, 2.0, 3.0],
    "merge_gap_s": [1.0, 2.0, 3.0],
    "min_len_s": [4.0, 6.0, 8.0],
}
PADS = [(0.5, 1.0), (1.0, 1.0), (1.5, 2.0)]
DEAD_WEIGHT = 2.0


def evaluate(sig, params, pad, labels, fps, top_n):
    params = calibrate(sig, params, fps)
    _, segs = build_segments(sig, params, fps)
    add_scores(segs)
    m = label_metrics(segs, labels, *pad)
    reel = label_metrics(top_segments(segs, top_n), labels, *pad)
    return {**m, "reel_precision": reel["precision"], "count": len(segs), "on": params["on"],
            "score": m["rally_cov"] - DEAD_WEIGHT * m["dead_leak"]}


def describe(m, params, pad):
    keys = ", ".join(f"{k}={v}" for k, v in params.items() if k in GRID)
    return (f"rally_cov {m['rally_cov']:4.0%} dead_leak {m['dead_leak']:4.0%} reel_prec {m['reel_precision']:4.0%} "
            f"rallies {m['count']:3d} on={m['on']} | {keys} pad={pad}")


def main(work, config, top="10"):
    work, cfg = Path(work), json.loads(Path(config).read_text())
    sig = dict(np.load(work / "signals.npz"))
    labels = load_labels(work.parent / "labels.csv")
    if not labels:
        sys.exit(f"no labels at {work.parent / 'labels.csv'}")
    fps, top_n = 1 / (sig["t"][1] - sig["t"][0]), cfg["export"]["top_n"]
    current_pad = (cfg["export"]["pad_before_s"], cfg["export"]["pad_after_s"])
    print("current:", describe(evaluate(sig, cfg["segment"], current_pad, labels, fps, top_n), cfg["segment"], current_pad))
    results = []
    for values in itertools.product(*GRID.values()):
        params = {**cfg["segment"], **dict(zip(GRID, values))}
        results += [(evaluate(sig, params, pad, labels, fps, top_n), params, pad) for pad in PADS]
    results.sort(key=lambda r: (-np.nan_to_num(r[0]["score"]), -np.nan_to_num(r[0]["reel_precision"])))
    for m, params, pad in results[: int(top)]:
        print(describe(m, params, pad))


if __name__ == "__main__":
    main(*sys.argv[1:])
