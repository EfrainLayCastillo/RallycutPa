import numpy as np

from signals import ENV_HZ, build_masks, detect_hits, frame_features, pool_to_frames

CFG = {
    "source_size": [1280, 720],
    "roi": [[0, 0], [1280, 0], [1280, 720], [0, 720]],
    "net_y": 360,
    "scoreboard": [0, 0, 100, 50],
}


def test_build_masks_splits_roi_at_net_and_scales_to_proxy():
    near, far, board = build_masks(CFG, (360, 640))
    assert near.shape == (360, 640)
    assert not (near & far).any()
    assert near[200:].all() and not near[:180].any()
    assert far[:180].all()
    assert board == (slice(0, 25), slice(0, 50))


def test_build_masks_without_scoreboard():
    assert build_masks({**CFG, "scoreboard": None}, (360, 640))[2] is None


def test_frame_features_measures_motion_per_half():
    masks = build_masks(CFG, (360, 640))
    prev = np.zeros((360, 640), np.float32)
    gray = prev.copy()
    gray[300:340, 100:200] = 255
    near, far, shake, board = frame_features(prev, gray, masks)
    assert near > 0 and far == 0 and board == 0


def test_detect_hits_finds_isolated_transients():
    env = np.full(ENV_HZ * 10, -50.0)
    env[[ENV_HZ * 2, ENV_HZ * 5, ENV_HZ * 8]] = -20.0
    assert detect_hits(env).tolist() == [2.0, 5.0, 8.0]


def test_pool_to_frames_takes_max_and_pads():
    env = np.arange(ENV_HZ * 2, dtype=float)
    pooled = pool_to_frames(env, n_frames=12, fps=5)
    assert len(pooled) == 12
    assert pooled[0] == ENV_HZ / 5 - 1
    assert pooled[-1] == pooled[:10].min()
