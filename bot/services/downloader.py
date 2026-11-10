import asyncio
import re
from datetime import datetime, timedelta
from pathlib import Path

URL_RE = re.compile(
    r"https?://(?:www\.)?(?:"
    r"youtu\.be/[A-Za-z0-9_\-]{6,}"
    r"|youtube\.com/watch\?[^\s]*v=[A-Za-z0-9_\-]{6,}"
    r"|youtube\.com/shorts/[A-Za-z0-9_\-]{6,}"
    r"|instagram\.com/(?:reel|reels|p)/[A-Za-z0-9_\-.]+"
    r")[^\s]*"
)

SIZE_LIMIT_BYTES = 48 * 1024 * 1024
STAGES = [
    {"scale": 720, "crf": 30},
    {"scale": 480, "crf": 33},
    {"scale": 360, "crf": 36},
]
DOWNLOAD_TIMEOUT = 300.0


class VideoError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class VideoTooBig(VideoError):
    pass


def extract_video_url(text: str) -> str | None:
    m = URL_RE.search(text)
    return m.group(0) if m else None


def next_stage_index(size_bytes: int, stage_index: int) -> int | None:
    if size_bytes <= SIZE_LIMIT_BYTES:
        return None
    if stage_index >= len(STAGES):
        return None
    return stage_index


class UrlCache:
    def __init__(self, ttl_seconds: int = 600):
        self._ttl = timedelta(seconds=ttl_seconds)
        self._items: dict[tuple[int, str], datetime] = {}

    def seen_recently(self, chat_id: int, url: str, now: datetime) -> bool:
        self._purge(now)
        return (chat_id, url) in self._items

    def mark(self, chat_id: int, url: str, now: datetime) -> None:
        self._purge(now)
        self._items[(chat_id, url)] = now

    def _purge(self, now: datetime) -> None:
        cutoff = now - self._ttl
        self._items = {k: v for k, v in self._items.items() if v > cutoff}


async def _run(cmd: list[str], timeout: float, what: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout)
    except TimeoutError:
        proc.kill()
        raise VideoError(f"{what}: timeout")
    if proc.returncode != 0:
        tail = (stderr or b"").decode(errors="replace")[-300:]
        raise VideoError(f"{what}: {tail.strip() or 'unknown error'}")


async def download_video(url: str, out_dir: Path,
                         cookies: Path | None = None,
                         timeout: float = DOWNLOAD_TIMEOUT) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    before = set(out_dir.glob("*.mp4"))
    cmd = [
        "yt-dlp",
        "-f", "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]/b",
        "--merge-output-format", "mp4",
        "--no-playlist",
        "-o", str(out_dir / "%(id)s.%(ext)s"),
    ]
    if cookies and Path(cookies).exists():
        cmd += ["--cookies", str(cookies)]
    cmd.append(url)
    await _run(cmd, timeout, "download")
    after = set(out_dir.glob("*.mp4"))
    new = [p for p in after - before]
    if not new:
        candidates = sorted(after, key=lambda p: p.stat().st_mtime)
        if not candidates:
            raise VideoError("download: no output file")
        new = [candidates[-1]]
    return max(new, key=lambda p: p.stat().st_mtime)


async def compress_video(src: Path, dst: Path, stage: dict,
                         timeout: float = 600.0) -> Path:
    dst = Path(dst)
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-vf", f"scale=-2:{stage['scale']}",
        "-c:v", "libx264", "-crf", str(stage["crf"]), "-preset", "fast",
        "-c:a", "aac", "-b:a", "96k",
        "-movflags", "+faststart",
        str(dst),
    ]
    await _run(cmd, timeout, "compress")
    return dst


async def process_video(url: str, workdir: Path,
                        cookies: Path | None = None) -> Path:
    workdir = Path(workdir)
    current = await download_video(url, workdir, cookies)
    try:
        stage_index = 0
        while current.stat().st_size > SIZE_LIMIT_BYTES:
            if stage_index >= len(STAGES):
                raise VideoTooBig("exceeds size limit after all compression stages")
            compressed = await compress_video(
                current, workdir / f"compressed_{stage_index}.mp4", STAGES[stage_index])
            if current != compressed and current.exists():
                current.unlink()
            current = compressed
            stage_index += 1
        return current
    except (VideoTooBig, VideoError):
        for f in workdir.glob("*.mp4"):
            f.unlink(missing_ok=True)
        raise
    except Exception as e:
        for f in workdir.glob("*.mp4"):
            f.unlink(missing_ok=True)
        raise VideoError(str(e)) from e
