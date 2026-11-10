from pathlib import Path

from bot.handlers.video import cleanup_workdirs


def _make_dir(base: Path, name: str) -> Path:
    d = base / name
    d.mkdir(parents=True)
    (d / "video.mp4").write_bytes(b"x")
    return d


def test_cleanup_removes_only_matching_chat(tmp_path):
    tmp = tmp_path / "data" / "tmp"
    _make_dir(tmp, "1_100")
    _make_dir(tmp, "1_101")
    keep = _make_dir(tmp, "2_100")
    _make_dir(tmp, "1_102")

    cleanup_workdirs(tmp_path / "data", 1)

    remaining = sorted(p.name for p in tmp.iterdir())
    assert remaining == ["2_100"]
    assert (keep / "video.mp4").exists()
