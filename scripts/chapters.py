# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Find the chapter files a camera split one recording into (GoPro by name, DJI and others by timestamps).
Prints the chapter paths in recording order, one per line (just the input when it was not split)."""
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

VIDEO_SUFFIXES = {".mp4", ".mov"}
GOPRO_NAME = re.compile(r"^G[HXP](\d{2})(\d{4})\.MP4$", re.IGNORECASE)
CONTIGUITY_TOLERANCE_S = 3.0


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration:format_tags=creation_time:stream=codec_name,width,height",
                          "-select_streams", "v:0", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    info = json.loads(out)
    stream, fmt = info["streams"][0], info["format"]
    created = fmt.get("tags", {}).get("creation_time")
    return {
        "path": Path(path),
        "duration": float(fmt["duration"]),
        "created": datetime.fromisoformat(created.replace("Z", "+00:00")) if created else None,
        "format": (stream["codec_name"], stream["width"], stream["height"]),
    }


def gopro_chapters(video):
    match = GOPRO_NAME.match(video.name)
    siblings = [p for p in video.parent.iterdir() if (m := GOPRO_NAME.match(p.name)) and m[2] == match[2]]
    return sorted(siblings, key=lambda p: int(GOPRO_NAME.match(p.name)[1]))


def contiguous(prev, nxt):
    gap = (nxt["created"] - prev["created"]).total_seconds() - prev["duration"]
    return abs(gap) <= CONTIGUITY_TOLERANCE_S


def chain_containing(items, target):
    """Group clips that start where the previous one ended; return the group that contains `target`."""
    chains = []
    for item in sorted(items, key=lambda i: i["created"]):
        if chains and contiguous(chains[-1][-1], item):
            chains[-1].append(item)
        else:
            chains.append([item])
    return next(c for c in chains if any(i["path"] == target for i in c))


def timestamp_chapters(video):
    target = probe(video)
    if target["created"] is None:
        return [video]
    siblings = [p for p in video.parent.iterdir() if p.suffix.lower() in VIDEO_SUFFIXES and p != video]
    candidates = [target] + [i for i in map(probe, siblings) if i["created"] and i["format"] == target["format"]]
    return [i["path"] for i in chain_containing(candidates, video)]


def find_chapters(video):
    video = Path(video)
    return gopro_chapters(video) if GOPRO_NAME.match(video.name) else timestamp_chapters(video)


if __name__ == "__main__":
    print("\n".join(str(p) for p in find_chapters(sys.argv[1])))
