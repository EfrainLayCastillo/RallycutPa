# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy", "matplotlib"]
# ///
"""Rally detection from signals.npz, scoring, evaluation against scoreboard changes, plots."""
import csv
import json
import sys
from pathlib import Path

import matplotlib
import numpy as np

from labels import label_metrics, load_labels

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SCOREBOARD_LAG_S = (-1, 10)
CHEER_WINDOW_S = 3
PLOT_CHUNK_S = 360


def activity(sig, smooth_s, fps):
    norm = lambda x: x / max(np.percentile(x, 95), 1e-6)
    combined = 0.5 * (norm(sig["near"]) + norm(sig["far"]))
    win = max(1, int(smooth_s * fps))
    return np.convolve(combined, np.ones(win) / win, mode="same")


def hysteresis_runs(a, on, off):
    runs, start = [], None
    for i, v in enumerate(a):
        if start is None and v >= on:
            start = i
        elif start is not None and v < off:
            runs.append((start, i))
            start = None
    return runs + ([(start, len(a))] if start is not None else [])


def merge_spans(spans, gap):
    merged = []
    for start, end in spans:
        if merged and start - merged[-1][1] < gap:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def describe(sig, a, start, end):
    t, hits = sig["t"], sig["hits"]
    inside = (t >= start) & (t <= end)
    after = (t > end) & (t <= end + CHEER_WINDOW_S)
    return {
        "start": round(float(start), 2),
        "end": round(float(end), 2),
        "duration": round(float(end - start), 2),
        "hits": int(((hits >= start) & (hits <= end)).sum()),
        "motion_peak": round(float(a[inside].max()), 3),
        "cheer_db": round(float(sig["audio_db"][after].max()), 1) if after.any() else 0.0,
    }


def build_segments(sig, p, fps):
    a = activity(sig, p["smooth_s"], fps)
    t = sig["t"]
    spans = merge_spans([(t[s], t[e - 1]) for s, e in hysteresis_runs(a, p["on"], p["off"])], p["merge_gap_s"])
    segs = [describe(sig, a, s, e) for s, e in spans if e - s >= p["min_len_s"]]
    if len(sig["hits"]):
        segs = [s for s in segs if s["hits"] >= p["min_hits"]]
    return a, segs


def expected_rallies(p, duration_s):
    return round(duration_s / 60 * p["points_per_min"])


def calibrate(sig, p, fps):
    """Pick the `on` threshold whose rally count is closest to the expected points for this video length."""
    if not p.get("points_per_min"):
        return p
    target = expected_rallies(p, sig["t"][-1])
    with_on = lambda on: {**p, "on": round(on, 2), "off": round(on * p["off_ratio"], 2)}
    candidates = [with_on(on) for on in np.arange(0.3, 1.5, 0.05)]
    return min(candidates, key=lambda c: abs(len(build_segments(sig, c, fps)[1]) - target))


def top_segments(segs, n):
    return sorted(segs, key=lambda s: -s["score"])[:n]


def add_scores(segs):
    keys = ["hits", "duration", "motion_peak", "cheer_db"]
    rank = lambda v: np.argsort(np.argsort(v)) / max(len(v) - 1, 1)
    total = sum(rank(np.array([s[k] for s in segs])) for k in keys) if segs else []
    for seg, value in zip(segs, total):
        seg["score"] = round(float(value) / len(keys), 3)


def board_events(sig, threshold, dedup_s=3):
    times = sig["t"][sig["board"] > threshold]
    return np.array([x for i, x in enumerate(times) if i == 0 or x - times[i - 1] > dedup_s])


def evaluate(segs, events, duration):
    lo, hi = SCOREBOARD_LAG_S
    ends = np.array([s["end"] for s in segs])
    within = lambda x, arr, a, b: bool(((arr >= x + a) & (arr <= x + b)).any())
    recall = np.mean([within(e, ends, -hi, -lo) for e in events]) if len(events) and len(ends) else 0
    precision = np.mean([within(x, events, lo, hi) for x in ends]) if len(ends) and len(events) else 0
    print(f"scoreboard events: {len(events)} | vs scoreboard (end within {lo}..+{hi}s): precision {precision:.0%}  recall {recall:.0%}")



def fmt(s):
    return f"{int(s // 60)}:{int(s % 60):02d}"


def plot_chunk(sig, a, segs, events, p, start, out):
    t = sig["t"]
    sel = (t >= start) & (t < start + PLOT_CHUNK_S)
    fig, ax = plt.subplots(2, 1, figsize=(22, 6), sharex=True)
    ax[0].plot(t[sel], a[sel], lw=0.7)
    ax[0].axhline(p["on"], color="g", lw=0.6)
    ax[0].axhline(p["off"], color="r", lw=0.6)
    ax[1].plot(t[sel], sig["audio_db"][sel], lw=0.5, color="tab:green")
    hits = sig["hits"][(sig["hits"] >= start) & (sig["hits"] < start + PLOT_CHUNK_S)]
    ax[1].plot(hits, np.full(len(hits), sig["audio_db"].max()), "|", color="k")
    for seg in segs:
        for axis in ax:
            axis.axvspan(seg["start"], seg["end"], color="orange", alpha=0.25)
    for e in events[(events >= start) & (events < start + PLOT_CHUNK_S)]:
        for axis in ax:
            axis.axvline(e, color="k", ls="--", lw=0.8)
    ticks = np.arange(start, start + PLOT_CHUNK_S + 1, 10)
    ax[1].set_xticks(ticks, [fmt(x) for x in ticks], rotation=90, fontsize=7)
    ax[1].set_xlim(start, start + PLOT_CHUNK_S)
    ax[0].set_ylabel("activity")
    ax[1].set_ylabel("audio dB")
    fig.tight_layout()
    fig.savefig(out, dpi=80)
    plt.close(fig)


def write_csv(segs, path):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", *segs[0].keys()] if segs else ["id"])
        writer.writeheader()
        writer.writerows({"id": i, **s} for i, s in enumerate(segs))


def main(work, config):
    work, cfg = Path(work), json.loads(Path(config).read_text())
    sig = dict(np.load(work / "signals.npz"))
    fps = 1 / (sig["t"][1] - sig["t"][0])
    params = calibrate(sig, cfg["segment"], fps)
    a, segs = build_segments(sig, params, fps)
    add_scores(segs)
    if params.get("points_per_min"):
        print(f"auto: expected {expected_rallies(params, sig['t'][-1])} rallies "
              f"({params['points_per_min']}/min) -> on {params['on']} off {params['off']}")
    events = board_events(sig, cfg.get("board_threshold", 1.0))
    write_csv(segs, work / "segments.csv")
    if len(events):
        evaluate(segs, events, sig["t"][-1])
    kept = sum(s["duration"] for s in segs)
    print(f"rallies: {len(segs)} | kept {kept:.0f}s of {sig['t'][-1]:.0f}s ({kept / sig['t'][-1]:.0%})")
    report_labels(segs, load_labels(work.parent / "labels.csv"), cfg["export"])
    for i, start in enumerate(np.arange(0, sig["t"][-1], PLOT_CHUNK_S)):
        plot_chunk(sig, a, segs, events, params, start, work / f"segments_{i:02d}.png")
    top = top_segments(segs, cfg["export"]["top_n"])
    print("reel:", "  ".join(f"{fmt(s['start'])}-{fmt(s['end'])} ({s['score']})" for s in top))


def report_labels(segs, labels, export):
    if not labels:
        return
    pads = export["pad_before_s"], export["pad_after_s"]
    m = label_metrics(segs, labels, *pads)
    reel = label_metrics(top_segments(segs, export["top_n"]), labels, *pads)
    print(f"vs labels.csv ({len(labels)} intervals): rally_cov {m['rally_cov']:.0%} (higher=better)  "
          f"dead_leak {m['dead_leak']:.0%} (lower=better)")
    print(f"reel top {export['top_n']}: reel_precision {reel['precision']:.0%} "
          f"({reel['rally_s']:.0f}s rally / {reel['dead_s']:.0f}s dead labeled inside the reel)")


if __name__ == "__main__":
    main(*sys.argv[1:3])
