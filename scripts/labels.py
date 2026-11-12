"""Manual labels (labels.csv next to the video) and the metrics computed against them."""
import csv


def parse_time(text):
    minutes, _, seconds = text.strip().rpartition(":")
    return int(minutes or 0) * 60 + float(seconds)


def load_labels(path):
    if not path.exists():
        return []
    rows = csv.DictReader(line for line in open(path) if line.strip() and not line.startswith("#"))
    return [(parse_time(r["start"]), parse_time(r["end"]), r["label"].strip()) for r in rows]


def overlap(a, b):
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def covered_seconds(intervals, spans):
    return sum(overlap(i, sp) for i in intervals for sp in spans)


def ratio(part, total):
    return part / total if total else float("nan")


def label_metrics(segs, labels, pad_before=0.0, pad_after=0.0):
    """rally_cov: share of rally-labeled seconds kept. dead_leak: share of dead-labeled seconds kept.
    precision: share of labeled seconds inside the kept spans that are rally."""
    spans = [(s["start"] - pad_before, s["end"] + pad_after) for s in segs]
    pick = lambda name: [(s, e) for s, e, label in labels if label == name]
    rally, dead = pick("rally"), pick("dead")
    rally_s, dead_s = covered_seconds(rally, spans), covered_seconds(dead, spans)
    return {
        "rally_cov": ratio(rally_s, sum(e - s for s, e in rally)),
        "dead_leak": ratio(dead_s, sum(e - s for s, e in dead)),
        "precision": ratio(rally_s, rally_s + dead_s),
        "rally_s": rally_s,
        "dead_s": dead_s,
    }
