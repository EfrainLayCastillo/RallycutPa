from datetime import datetime, timedelta, timezone
from pathlib import Path

from chapters import chain_containing, find_chapters, gopro_chapters

T0 = datetime(2026, 11, 12, 18, 0, tzinfo=timezone.utc)


def clip(name, start_s, duration):
    return {"path": Path(name), "created": T0 + timedelta(seconds=start_s), "duration": duration}


def test_gopro_chapters_groups_by_file_number_and_orders_by_chapter(tmp_path):
    for name in ["GH020123.MP4", "GH010123.MP4", "GH030123.MP4", "GH010124.MP4", "notes.txt"]:
        (tmp_path / name).touch()
    chapters = gopro_chapters(tmp_path / "GH020123.MP4")
    assert [p.name for p in chapters] == ["GH010123.MP4", "GH020123.MP4", "GH030123.MP4"]


def test_find_chapters_uses_gopro_names_without_probing(tmp_path):
    for name in ["GX010007.MP4", "GX020007.MP4"]:
        (tmp_path / name).touch()
    assert [p.name for p in find_chapters(tmp_path / "GX010007.MP4")] == ["GX010007.MP4", "GX020007.MP4"]


def test_chain_containing_links_back_to_back_clips():
    a, b, c = clip("a", 0, 600), clip("b", 601, 600), clip("c", 1200, 300)
    other = clip("other", 5000, 100)
    assert [i["path"].name for i in chain_containing([c, other, a, b], Path("b"))] == ["a", "b", "c"]


def test_chain_containing_keeps_separate_recordings_apart():
    a, b = clip("a", 0, 600), clip("b", 700, 600)
    assert [i["path"].name for i in chain_containing([a, b], Path("b"))] == ["b"]
