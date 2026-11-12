import numpy as np
import pytest

from conftest import bursts, make_signals
from segment import (
    add_scores,
    board_events,
    build_segments,
    calibrate,
    expected_rallies,
    hysteresis_runs,
    merge_spans,
    top_segments,
)

PARAMS = {"smooth_s": 0.2, "on": 0.5, "off": 0.3, "merge_gap_s": 1.0, "min_len_s": 2.0, "min_hits": 0}


def test_hysteresis_runs_needs_on_to_start_and_off_to_stop():
    a = np.array([0.1, 0.6, 0.4, 0.4, 0.2, 0.4, 0.7, 0.8])
    assert hysteresis_runs(a, on=0.5, off=0.3) == [(1, 4), (6, 8)]


def test_merge_spans_joins_close_gaps_only():
    assert merge_spans([(0, 5), (5.5, 8), (12, 15)], gap=1.0) == [(0, 8), (12, 15)]


def test_build_segments_finds_each_burst():
    activity = bursts([(5, 15), (30, 40)], total_s=60)
    _, segs = build_segments(make_signals(activity, activity), PARAMS, fps=5)
    assert [(round(s["start"]), round(s["end"])) for s in segs] == [(5, 15), (30, 40)]


def test_build_segments_drops_short_bursts():
    activity = bursts([(5, 6), (30, 40)], total_s=60)
    _, segs = build_segments(make_signals(activity, activity), PARAMS, fps=5)
    assert len(segs) == 1


def test_build_segments_requires_hits_when_configured():
    activity = bursts([(5, 15), (30, 40)], total_s=60)
    sig = make_signals(activity, activity, hits=[6, 8, 10, 31])
    _, segs = build_segments(sig, {**PARAMS, "min_hits": 3}, fps=5)
    assert [s["hits"] for s in segs] == [3]


def test_expected_rallies_scales_with_duration():
    assert expected_rallies({"points_per_min": 1.7}, 90 * 60) == 153


def test_calibrate_without_prior_keeps_params():
    assert calibrate(make_signals([0.1] * 10, [0.1] * 10), PARAMS, fps=5) is PARAMS


def test_calibrate_picks_threshold_matching_expected_count():
    # Six strong rallies plus six weaker "walking" bursts in 6 minutes; 1/min expects only the strong ones.
    strong = [(i * 60 + 5, i * 60 + 20) for i in range(6)]
    weak = [(i * 60 + 35, i * 60 + 45) for i in range(6)]
    activity = bursts(strong, 360, high=1.0) + bursts(weak, 360, high=0.5, low=0.0)
    sig = make_signals(activity, activity)
    params = calibrate(sig, {**PARAMS, "points_per_min": 1.0, "off_ratio": 0.6}, fps=5)
    _, segs = build_segments(sig, params, fps=5)
    assert len(segs) == 6
    assert all(s["start"] % 60 < 30 for s in segs)


def test_add_scores_ranks_longer_and_stronger_rallies_higher():
    segs = [
        {"hits": 2, "duration": 5, "motion_peak": 0.5, "cheer_db": -40},
        {"hits": 9, "duration": 20, "motion_peak": 1.2, "cheer_db": -20},
    ]
    add_scores(segs)
    assert segs[1]["score"] == 1.0 and segs[0]["score"] == 0.0
    assert top_segments(segs, 1) == [segs[1]]


def test_add_scores_handles_empty():
    segs = []
    add_scores(segs)
    assert segs == []


def test_board_events_deduplicates_close_changes():
    sig = make_signals([0] * 50, [0] * 50)
    sig["board"][[5, 6, 7, 40]] = 0.5
    assert board_events(sig, threshold=0.1, dedup_s=3).tolist() == pytest.approx([1.2, 8.2])
