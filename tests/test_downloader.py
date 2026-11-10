import asyncio
import os
import shutil
import stat
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bot.services.downloader import (
    SIZE_LIMIT_BYTES, STAGES, UrlCache, VideoTooBig, compress_video,
    download_video, extract_video_url, next_stage_index, process_video,
)

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("text,expected", [
    ("смотри https://youtu.be/dQw4w9WgXcQ лол", "https://youtu.be/dQw4w9WgXcQ"),
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&si=x", "https://www.youtube.com/watch?v=dQw4w9WgXcQ&si=x"),
    ("тут https://youtube.com/shorts/dQw4w9WgXcQ ок", "https://youtube.com/shorts/dQw4w9WgXcQ"),
    ("реел https://www.instagram.com/reel/ABC123xyz/ да", "https://www.instagram.com/reel/ABC123xyz/"),
    ("пост https://instagram.com/p/ABC123xyz/", "https://instagram.com/p/ABC123xyz/"),
])
def test_extract_video_url_positive(text, expected):
    assert extract_video_url(text) == expected


@pytest.mark.parametrize("text", [
    "просто текст",
    "https://youtube.com/channel/UC123",
    "https://instagram.com/user/",
    "ftp://youtu.be/dQw4w9WgXcQ",
    "https://notyoutube.com/watch?v=dQw4w9WgXcQ",
])
def test_extract_video_url_negative(text):
    assert extract_video_url(text) is None


def test_next_stage_index():
    assert next_stage_index(SIZE_LIMIT_BYTES, 0) is None
    assert next_stage_index(SIZE_LIMIT_BYTES + 1, 0) == 0
    assert next_stage_index(SIZE_LIMIT_BYTES + 1, len(STAGES)) is None


def test_url_cache_ttl():
    cache = UrlCache(ttl_seconds=600)
    cache.mark(1, "https://youtu.be/x", NOW)
    assert cache.seen_recently(1, "https://youtu.be/x", NOW + timedelta(seconds=599))
    assert not cache.seen_recently(1, "https://youtu.be/x", NOW + timedelta(seconds=601))
    assert not cache.seen_recently(2, "https://youtu.be/x", NOW)
    assert not cache.seen_recently(1, "https://youtu.be/y", NOW)


def _make_fake_ytdlp(bin_dir: Path, fixture: Path) -> Path:
    script = bin_dir / "yt-dlp"
    script.write_text(
        "#!/bin/sh\n"
        'while [ "$#" -gt 0 ]; do\n'
        '  if [ "$1" = "-o" ]; then\n'
        f'    cp "{fixture}" "$(dirname "$2")/out.mp4"\n'
        "    exit 0\n"
        "  fi\n"
        "  shift\n"
        "done\n"
        "exit 1\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def test_download_video_with_fake_ytdlp(tmp_path, monkeypatch):
    fixture = tmp_path / "fixture.mp4"
    fixture.write_bytes(b"fake video bytes")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _make_fake_ytdlp(bin_dir, fixture)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

    out = asyncio.run(download_video("https://youtu.be/x", tmp_path / "out"))
    assert out.read_bytes() == b"fake video bytes"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_process_video_compresses_oversized(tmp_path, monkeypatch):
    fixture = tmp_path / "fixture.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=640x480:rate=10",
         "-pix_fmt", "yuv420p", str(fixture)],
        check=True, capture_output=True,
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _make_fake_ytdlp(bin_dir, fixture)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

    import bot.services.downloader as downloader_module
    monkeypatch.setattr(downloader_module, "SIZE_LIMIT_BYTES", fixture.stat().st_size - 1)

    out = asyncio.run(process_video("https://youtu.be/x", tmp_path / "work", cookies=None))
    assert out.exists()
    assert out.stat().st_size <= downloader_module.SIZE_LIMIT_BYTES
