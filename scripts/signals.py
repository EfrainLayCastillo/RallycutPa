# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy", "scipy", "opencv-python-headless"]
# ///
"""Per-frame features from the proxy: ROI motion (near/far half), camera shake, scoreboard change, audio."""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from scipy.io import wavfile
from scipy.ndimage import median_filter
from scipy.signal import butter, find_peaks, sosfilt

DIFF_THRESHOLD = 25
BOARD_PIXEL_DELTA = 40
ENV_HZ = 100
HIT_RISE_DB = 12


def build_masks(cfg, shape):
    scale = shape[1] / cfg["source_size"][0]
    roi = np.zeros(shape, np.uint8)
    cv2.fillPoly(roi, [(np.array(cfg["roi"]) * scale).astype(np.int32)], 1)
    roi = roi.astype(bool)
    near = roi.copy()
    near[: int(cfg["net_y"] * scale)] = False
    board = None
    if cfg.get("scoreboard"):
        x0, y0, x1, y1 = (int(v * scale) for v in cfg["scoreboard"])
        board = (slice(y0, y1), slice(x0, x1))
    return near, roi & ~near, board


def frame_features(prev, gray, masks):
    near, far, board = masks
    moved = np.abs(gray - prev) > DIFF_THRESHOLD
    (dx, dy), _ = cv2.phaseCorrelate(prev, gray)
    board_change = 0.0
    if board is not None:
        board_change = (np.abs(gray[board] - prev[board]) > BOARD_PIXEL_DELTA).mean()
    return moved[near].mean(), moved[far].mean(), np.hypot(dx, dy), board_change


def motion_features(proxy, cfg):
    cap = cv2.VideoCapture(str(proxy))
    fps = cap.get(cv2.CAP_PROP_FPS)
    rows, prev, masks = [], None, None
    while (frame := cap.read()[1]) is not None:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
        if prev is None:
            masks = build_masks(cfg, gray.shape)
        else:
            rows.append(frame_features(prev, gray, masks))
        prev = gray
    feats = np.array(rows)
    return (np.arange(len(feats)) + 1) / fps, feats


def audio_envelope_db(wav):
    rate, data = wavfile.read(wav)
    x = sosfilt(butter(4, 1500, "highpass", fs=rate, output="sos"), data.astype(np.float32) / 32768)
    hop = rate // ENV_HZ
    frames = x[: len(x) // hop * hop].reshape(-1, hop)
    return 20 * np.log10(np.sqrt((frames**2).mean(axis=1)) + 1e-6)


def detect_hits(env_db):
    baseline = median_filter(env_db, size=ENV_HZ * 2)
    peaks, _ = find_peaks(env_db - baseline, height=HIT_RISE_DB, distance=ENV_HZ // 4)
    return peaks / ENV_HZ


def pool_to_frames(env_db, n_frames, fps):
    hop = int(round(ENV_HZ / fps))
    pooled = env_db[: len(env_db) // hop * hop].reshape(-1, hop).max(axis=1)
    return np.pad(pooled, (0, max(0, n_frames - len(pooled))), constant_values=pooled.min())[:n_frames]


def main(work, config):
    work, cfg = Path(work), json.loads(Path(config).read_text())
    t, feats = motion_features(work / "proxy.mp4", cfg)
    fps = 1 / (t[1] - t[0])
    audio_db, hits = np.zeros(len(t)), np.array([])
    if (work / "audio16k.wav").exists():
        env = audio_envelope_db(work / "audio16k.wav")
        audio_db, hits = pool_to_frames(env, len(t), fps), detect_hits(env)
    np.savez(work / "signals.npz", t=t, near=feats[:, 0], far=feats[:, 1], shake=feats[:, 2],
             board=feats[:, 3], audio_db=audio_db, hits=hits)
    print(f"signals: {len(t)} frames ({t[-1]:.0f}s @ {fps:.0f}fps), {len(hits)} audio hits")


if __name__ == "__main__":
    main(*sys.argv[1:3])
