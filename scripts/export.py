# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Encode rally clips and concatenate them into a top-N reel (and optionally the clean match)."""
import csv
import json
import subprocess
import sys
from pathlib import Path


def pick_encoder():
    encoders = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    if "h264_videotoolbox" in encoders:
        return ["-c:v", "h264_videotoolbox", "-b:v", "8M"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]


def encode_clip(meta, start, end, out, encoder):
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-i", meta["video"]]
    if meta.get("audio"):
        cmd += ["-ss", f"{start:.2f}", "-i", meta["audio"], "-map", "0:v:0", "-map", "1:a:0"]
    else:
        cmd += ["-map", "0:v:0", "-map", "0:a:0?"]
    if meta.get("lut"):
        cmd += ["-vf", f"lut3d={meta['lut']}"]
    cmd += ["-t", f"{end - start:.2f}", *encoder, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", str(out)]
    subprocess.run(cmd, check=True)


def concat(clips, out):
    listing = out.with_suffix(".txt")
    listing.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-c", "copy", str(out)], check=True)
    listing.unlink()


def export_rallies(rallies, meta, pad, clips_dir, encoder):
    clips = []
    for r in sorted(rallies, key=lambda r: float(r["start"])):
        start = max(0.0, float(r["start"]) - pad["pad_before_s"])
        end = float(r["end"]) + pad["pad_after_s"]
        out = clips_dir / f"rally_{int(r['id']):03d}.mp4"
        if not out.exists():
            encode_clip(meta, start, end, out, encoder)
        clips.append(out)
    return clips


def main(work, config, *flags):
    work, cfg = Path(work), json.loads(Path(config).read_text())
    meta = json.loads((work / "meta.json").read_text())
    rallies = list(csv.DictReader(open(work / "segments.csv")))
    clips_dir = work / "clips"
    clips_dir.mkdir(exist_ok=True)
    for old in clips_dir.glob("*.mp4"):
        old.unlink()
    encoder, pad = pick_encoder(), cfg["export"]
    top = sorted(rallies, key=lambda r: -float(r["score"]))[: pad["top_n"]]
    concat(export_rallies(top, meta, pad, clips_dir, encoder), work / "reel_top.mp4")
    print(f"reel: {work / 'reel_top.mp4'} ({len(top)} rallies, encoder {encoder[1]})")
    if "--all" in flags:
        concat(export_rallies(rallies, meta, pad, clips_dir, encoder), work / "match_clean.mp4")
        print(f"clean match: {work / 'match_clean.mp4'} ({len(rallies)} rallies)")


if __name__ == "__main__":
    main(*sys.argv[1:])
