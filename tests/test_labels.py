import math

import pytest

from labels import label_metrics, load_labels, overlap, parse_time


@pytest.mark.parametrize("text, expected", [("2:10", 130), ("0:05", 5), ("12", 12), ("1:02.5", 62.5)])
def test_parse_time(text, expected):
    assert parse_time(text) == expected


def test_load_labels_skips_comments_and_blank_lines(tmp_path):
    path = tmp_path / "labels.csv"
    path.write_text("# comment\nstart,end,label\n\n0:10,0:20,rally\n0:20,0:25, dead\n")
    assert load_labels(path) == [(10, 20, "rally"), (20, 25, "dead")]


def test_load_labels_missing_file(tmp_path):
    assert load_labels(tmp_path / "nope.csv") == []


def test_overlap():
    assert overlap((0, 10), (5, 20)) == 5
    assert overlap((0, 10), (10, 20)) == 0
    assert overlap((0, 10), (2, 3)) == 1


def test_label_metrics_counts_rally_and_dead_seconds():
    labels = [(10, 20, "rally"), (20, 30, "dead"), (40, 50, "rally")]
    segs = [{"start": 10, "end": 25}]
    m = label_metrics(segs, labels)
    assert m["rally_cov"] == pytest.approx(10 / 20)
    assert m["dead_leak"] == pytest.approx(5 / 10)
    assert m["precision"] == pytest.approx(10 / 15)


def test_label_metrics_applies_padding():
    labels = [(10, 20, "rally"), (20, 30, "dead")]
    m = label_metrics([{"start": 12, "end": 18}], labels, pad_before=2, pad_after=4)
    assert m["rally_cov"] == pytest.approx(1.0)
    assert m["dead_leak"] == pytest.approx(0.2)


def test_label_metrics_without_overlap_is_nan_precision():
    m = label_metrics([{"start": 100, "end": 110}], [(0, 10, "rally")])
    assert m["rally_cov"] == 0
    assert math.isnan(m["precision"])
