from export import clip_command

ENCODER = ["-c:v", "libx264"]


def test_clip_command_uses_video_audio_by_default():
    cmd = clip_command({"video": "v.mp4", "audio": None}, 10, 15, "out.mp4", ENCODER)
    assert cmd[cmd.index("-ss") + 1] == "10.00"
    assert "0:a:0?" in cmd
    assert cmd[cmd.index("-t") + 1] == "5.00"
    assert "-vf" not in cmd


def test_clip_command_maps_separate_audio_file():
    cmd = clip_command({"video": "v.mp4", "audio": "a.m4a"}, 10, 15, "out.mp4", ENCODER)
    assert cmd.count("-i") == 2 and "a.m4a" in cmd
    assert "1:a:0" in cmd


def test_clip_command_applies_lut():
    cmd = clip_command({"video": "v.mp4", "lut": "luts/dji-dlogm.cube"}, 0, 5, "out.mp4", ENCODER)
    assert cmd[cmd.index("-vf") + 1] == "lut3d=luts/dji-dlogm.cube"
