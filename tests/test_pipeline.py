"""End-to-end checks of scripts/pipeline.sh on a tiny synthetic video. Needs ffmpeg (run inside the tools container)."""
import json
import shutil
import subprocess

import numpy as np
import pytest

from conftest import ROOT, requires_ffmpeg

pytestmark = requires_ffmpeg


def make_video(path, handler=None):
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30:duration=4",
           "-f", "lavfi", "-i", "sine=frequency=440:duration=4", "-c:v", "libx264", "-c:a", "aac", "-shortest"]
    if handler:
        cmd += ["-metadata:s:v:0", f"handler_name={handler}"]
    subprocess.run([*cmd, str(path)], check=True)


def identity_lut(path):
    rows = [f"{r} {g} {b}" for b in (0, 1) for g in (0, 1) for r in (0, 1)]
    path.write_text("LUT_3D_SIZE 2\n" + "\n".join(rows) + "\n")


def run_pipeline(*args, config):
    env = {"CONFIG": str(config), "PATH": "/usr/local/bin:/usr/bin:/bin"}
    return subprocess.run(["bash", str(ROOT / "scripts/pipeline.sh"), *args], env=env,
                          capture_output=True, text=True, check=True).stdout


@pytest.fixture
def camera_config(tmp_path):
    cfg = json.loads((ROOT / "config/camera-glass.json").read_text())
    luts = tmp_path / "luts"
    luts.mkdir()
    identity_lut(luts / "gopro.cube")
    cfg["luts"] = {"gopro": str(luts / "gopro.cube"), "dji": str(luts / "missing.cube")}
    path = tmp_path / "camera.json"
    path.write_text(json.dumps(cfg))
    return path


@pytest.mark.parametrize("handler, camera, has_lut", [
    ("GoPro AVC", "gopro", True),
    ("DJI.AVC", "dji", False),
    (None, "unknown", False),
])
def test_prepare_detects_camera_and_lut(tmp_path, camera_config, handler, camera, has_lut):
    video = tmp_path / "game.mp4"
    make_video(video, handler)
    out = run_pipeline("prepare", str(video), config=camera_config)
    meta = json.loads((tmp_path / "work/meta.json").read_text())
    assert meta["camera"] == camera
    assert bool(meta["lut"]) == has_lut
    assert f"camera: {camera}" in out
    assert (tmp_path / "work/proxy.mp4").exists()
    assert (tmp_path / "work/audio16k.wav").exists()


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv not installed")
def test_signals_and_segment_run_on_prepared_video(tmp_path, camera_config):
    video = tmp_path / "game.mp4"
    make_video(video)
    run_pipeline("prepare", str(video), config=camera_config)
    run_pipeline("signals", str(video), config=camera_config)
    sig = np.load(tmp_path / "work/signals.npz")
    assert len(sig["t"]) == len(sig["near"]) > 10
    out = run_pipeline("segment", str(video), config=camera_config)
    assert "rallies:" in out
    assert (tmp_path / "work/segments.csv").exists()


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv not installed")
def test_run_goes_end_to_end_with_all_flag(tmp_path, camera_config):
    video = tmp_path / "game.mp4"
    make_video(video)
    run_pipeline("run", str(video), "--all", config=camera_config)
    work = tmp_path / "work"
    for name in ("proxy.mp4", "signals.npz", "segments.csv", "meta.json"):
        assert (work / name).exists(), name
