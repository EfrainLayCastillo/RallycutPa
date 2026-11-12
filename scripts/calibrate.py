# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy", "opencv-python-headless"]
# ///
"""Derive a camera config (court ROI polygon + net line) from the video framing and render a preview."""
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ANALYSIS_WIDTH = 640
SAMPLES = 7
SEED_BOX = (0.40, 0.60, 0.85, 0.95)  # x0, x1, y0, y1 as frame fractions: floor right in front of the camera
HUE_TOL, SAT_TOL, VAL_TOL = 12, 70, 80
FAR_PLAYER_HEIGHT = 0.12  # of frame height: room above the far floor edge for far players' bodies
NET_HEIGHT = 0.075  # of frame height: from the net tape down to where the near court starts
NET_SEARCH = 0.35


def probe_video(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:format=duration", "-of", "json", str(video)],
                         capture_output=True, text=True, check=True).stdout
    info = json.loads(out)
    stream = info["streams"][0]
    return stream["width"], stream["height"], float(info["format"]["duration"])


def grab_frame(video, t):
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                          "-vf", f"scale={ANALYSIS_WIDTH}:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
                         capture_output=True, check=True).stdout
    return cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR)


def background(video, duration):
    """Median of frames spread over the video: players move, the court stays."""
    frames = [grab_frame(video, t) for t in np.linspace(0.1, 0.9, SAMPLES) * duration]
    return np.median(np.stack(frames), axis=0).astype(np.uint8)


def floor_mask(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(int)
    h, w = img.shape[:2]
    x0, x1, y0, y1 = SEED_BOX
    seed = np.median(hsv[int(y0 * h): int(y1 * h), int(x0 * w): int(x1 * w)].reshape(-1, 3), axis=0)
    dh = np.abs(hsv[..., 0] - seed[0])
    close = (np.minimum(dh, 180 - dh) <= HUE_TOL) & (np.abs(hsv[..., 1] - seed[1]) <= SAT_TOL) \
        & (np.abs(hsv[..., 2] - seed[2]) <= VAL_TOL)
    mask = cv2.morphologyEx(close.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    _, labels = cv2.connectedComponents(mask)
    return labels == labels[int((y0 + y1) / 2 * h), int((x0 + x1) / 2 * w)]


def floor_polygon(mask):
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    hull = cv2.convexHull(max(contours, key=cv2.contourArea))
    return cv2.approxPolyDP(hull, 0.01 * cv2.arcLength(hull, True), True).reshape(-1, 2)


def net_tape_row(img, mask, floor_top):
    """Row of the white net tape: the longest white horizontal band in the far part of the floor."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    white = (hsv[..., 2] > 180) & (hsv[..., 1] < 60)
    lo, hi = floor_top, floor_top + int(NET_SEARCH * (img.shape[0] - floor_top))
    span = mask[lo:hi].any(axis=0)
    counts = white[lo:hi][:, span].sum(axis=1)
    if counts.max() < 0.3 * span.sum():
        return floor_top + int(0.12 * (img.shape[0] - floor_top))
    return lo + int(np.argmax(counts))


def extend_above_floor(poly, roi_top):
    """Raise the far edge of the floor polygon so far players' bodies stay inside the ROI."""
    top_y = poly[:, 1].min()
    far = poly[poly[:, 1] <= top_y + 6]
    near = poly[poly[:, 1] > top_y + 6]
    xl, xr = far[:, 0].min(), far[:, 0].max()
    center = near.mean(axis=0)
    near = near[np.argsort(np.arctan2(near[:, 1] - center[1], near[:, 0] - center[0]))]
    right_first = np.roll(near, -int(np.argmax(near[:, 0] - near[:, 1])), axis=0)
    return np.array([[xl, roi_top], [xr, roi_top], [xr, top_y], *right_first, [xl, top_y]])


def calibrate(img):
    mask = floor_mask(img)
    poly = floor_polygon(mask)
    height = img.shape[0]
    floor_top = int(poly[:, 1].min())
    net_y = net_tape_row(img, mask, floor_top) + int(NET_HEIGHT * height)
    roi_top = max(0, int(floor_top - FAR_PLAYER_HEIGHT * height))
    return extend_above_floor(poly, roi_top), net_y


def render_preview(img, roi, net_y, out):
    preview = img.copy()
    cv2.polylines(preview, [roi.astype(np.int32)], True, (0, 255, 255), 2)
    cv2.line(preview, (0, net_y), (img.shape[1], net_y), (0, 0, 255), 1)
    cv2.imwrite(str(out), preview)


def write_config(template, roi, net_y, scale, size, out):
    cfg = json.loads(Path(template).read_text())
    cfg.update(source_size=list(size), roi=(roi * scale).round().astype(int).tolist(),
               net_y=int(round(net_y * scale)), scoreboard=None)
    Path(out).write_text(json.dumps(cfg, indent=2) + "\n")


def main(video, template, out_config, preview):
    width, height, duration = probe_video(video)
    img = background(video, duration)
    roi, net_y = calibrate(img)
    write_config(template, roi, net_y, width / img.shape[1], (width, height), out_config)
    render_preview(img, roi, net_y, preview)
    print(f"camera config: {out_config} (ROI {len(roi)} points, net_y {int(net_y * width / img.shape[1])})")
    print(f"check the overlay: {preview}")


if __name__ == "__main__":
    main(*sys.argv[1:5])
