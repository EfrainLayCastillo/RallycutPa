import cv2
import numpy as np

from calibrate import calibrate, floor_mask

H, W = 360, 640
FLOOR = [(240, 200), (400, 200), (640, 290), (640, 360), (0, 360), (0, 290)]
NET_TAPE_Y = 205


def synthetic_court():
    """Grey hall, blue trapezoid floor seen from the back glass, white net tape near the far edge."""
    img = np.full((H, W, 3), 90, np.uint8)
    cv2.fillPoly(img, [np.array(FLOOR, np.int32)], (200, 90, 30))
    cv2.line(img, (0, 320), (640, 320), (255, 255, 255), 2)
    cv2.line(img, (230, NET_TAPE_Y), (410, NET_TAPE_Y), (255, 255, 255), 2)
    return img


def test_floor_mask_keeps_the_court_floor_only():
    mask = floor_mask(synthetic_court())
    assert mask[340, 320] and mask[250, 320]
    assert not mask[100, 320] and not mask[210, 50]


def test_calibrate_finds_roi_and_net():
    roi, net_y = calibrate(synthetic_court())
    xs, ys = roi[:, 0], roi[:, 1]
    assert ys.min() < 200 - 0.1 * H
    assert ys.max() >= H - 2
    assert xs.min() <= 2 and xs.max() >= W - 3
    assert NET_TAPE_Y < net_y < NET_TAPE_Y + 0.1 * H
