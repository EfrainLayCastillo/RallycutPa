"""End-to-end checks of scripts/pipeline.sh on a tiny synthetic video. Needs ffmpeg (run inside the tools container)."""
import json
import shutil
import subprocess

import numpy as np
import pytest

from conftest import ROOT, requires_ffmpeg

pytestmark = requires_ffmpeg


def make_video(path, handler=None, duration=4, created=None):
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size=320x180:rate=30:duration={duration}",
           "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}", "-c:v", "libx264", "-c:a", "aac",
           "-shortest"]
    if handler:
        cmd += ["-metadata:s:v:0", f"handler_name={handler}"]
    if created:
        cmd += ["-metadata", f"creation_time={created}"]
    subprocess.run([*cmd, str(path)], check=True)


def identity_lut(path):
    rows = [f"{r} {g} {b}" for b in (0, 1) for g in (0, 1) for r in (0, 1)]
    path.write_text("LUT_3D_SIZE 2\n" + "\n".join(rows) + "\n")


def run_pipeline(*args, config):
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin"} | ({"CONFIG": str(config)} if config else {})
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


def duration_of(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


def test_prepare_merges_split_dji_recording(tmp_path, camera_config):
    make_video(tmp_path / "DJI_0001.MP4", "DJI.AVC", duration=3, created="2026-11-12T18:00:00Z")
    make_video(tmp_path / "DJI_0002.MP4", "DJI.AVC", duration=3, created="2026-11-12T18:00:03Z")
    make_video(tmp_path / "DJI_0099.MP4", "DJI.AVC", duration=3, created="2026-11-12T19:00:00Z")
    out = run_pipeline("prepare", str(tmp_path / "DJI_0001.MP4"), config=camera_config)
    meta = json.loads((tmp_path / "work/meta.json").read_text())
    assert "2 chapters" in out or meta["video"].endswith("source.mp4")
    assert meta["video"].endswith("work/source.mp4")
    assert duration_of(meta["video"]) == pytest.approx(6, abs=0.3)
    assert meta["camera"] == "dji"


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv not installed")
def test_prepare_without_config_writes_auto_camera_config(tmp_path):
    video = tmp_path / "game.mp4"
    make_video(video)
    run_pipeline("prepare", str(video), config=None)
    cfg = json.loads((tmp_path / "work/camera.json").read_text())
    assert len(cfg["roi"]) >= 4 and cfg["source_size"] == [320, 180]
    assert (tmp_path / "work/calibration.jpg").exists()
