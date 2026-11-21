"""Download, conversion, and file helpers for StreamTune.

This module intentionally does not import Streamlit, so it can be unit-tested
without starting a web server.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import static_ffmpeg
import yt_dlp
from yt_dlp.utils import sanitize_filename

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COOKIES_FILE = PROJECT_ROOT / "cookies.txt"
WORK_DIR = Path(tempfile.gettempdir()) / "streamtune"

FORMAT_MP3 = "MP3"
FORMAT_MP4 = "MP4"

# Option tables: value -> label. The first entry of each table is the default.
MP3_BITRATES: dict[str, str] = {
    "192": "192 kbps (balanced)",
    "320": "320 kbps (best quality)",
    "128": "128 kbps (smallest)",
}
MP4_HEIGHTS: dict[str, str] = {
    "best": "Best available",
    "2160": "2160p (4K)",
    "1440": "1440p",
    "1080": "1080p",
    "720": "720p",
    "480": "480p",
}

MIME_TYPES = {"mp3": "audio/mpeg", "mp4": "video/mp4"}
MAX_STEM_LENGTH = 120

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_ERROR_PREFIX_RE = re.compile(r"^ERROR:\s*")
_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

# (substrings to look for in the lower-cased error text, friendly message)
_ERROR_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("private video",), "This video is private."),
    (
        ("sign in", "login required", "cookies", "members-only", "members only"),
        "This video requires sign-in. Add a cookies.txt file to the project root (see README).",
    ),
    (
        ("available in your country", "geo-restricted", "geo restricted", "blocked in your country"),
        "This video is blocked in your region.",
    ),
    (
        ("video unavailable", "has been removed", "no longer available", "does not exist"),
        "This video is unavailable or was removed.",
    ),
    (("unsupported url",), "This link is not supported."),
    (
        ("http error 429", "too many requests"),
        "The site is rate-limiting requests. Wait a few minutes and try again.",
    ),
    (("ffmpeg",), "FFmpeg failed while processing the file."),
]

ProgressCallback = Callable[[float | None, str], None]


@dataclass(frozen=True)
class Download:
    """A finished conversion. The file lives in ``workdir`` until it is discarded."""

    url: str
    title: str
    filename: str
    path: Path
    mime: str
    workdir: Path


# ----------------------------------------------------------------------
# Input and metadata
# ----------------------------------------------------------------------
def validate_url(raw: str | None) -> str:
    """Return the cleaned URL or raise ``ValueError`` with a user-facing message."""
    url = (raw or "").strip()
    if not url:
        raise ValueError("Paste a media URL first.")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("That doesn't look like a valid http(s) URL.")
    return url


def fetch_info(url: str) -> dict:
    """Read title and preview metadata without downloading anything."""
    with yt_dlp.YoutubeDL(_base_options()) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        raise ValueError("No media information was returned for this link.")
    return {
        "title": info.get("title") or "",
        "thumbnail": info.get("thumbnail") or "",
        "duration": info.get("duration") or 0,
        "uploader": info.get("uploader") or info.get("channel") or "",
    }


def format_duration(seconds: float | int | None) -> str:
    if not seconds:
        return ""
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def quality_label(fmt: str, quality: str) -> str:
    table = MP3_BITRATES if fmt == FORMAT_MP3 else MP4_HEIGHTS
    return table.get(quality, quality)


# ----------------------------------------------------------------------
# Download and conversion
# ----------------------------------------------------------------------
def ensure_ffmpeg() -> str | None:
    """Make FFmpeg available on PATH (downloads a static build on first run)."""
    existing = shutil.which("ffmpeg")
    if not existing:
        try:
            static_ffmpeg.add_paths()
        except Exception:
            return None
        existing = shutil.which("ffmpeg")
    return str(Path(existing).parent) if existing else None


def cookies_path() -> str | None:
    return str(COOKIES_FILE) if COOKIES_FILE.is_file() else None


def format_selector(fmt: str, quality: str) -> str:
    """Build the yt-dlp format string for the chosen output and quality."""
    if fmt == FORMAT_MP3:
        return "bestaudio/best"
    if quality == "best":
        return "bv*+ba/b"
    # Prefer the requested height; if the source has nothing that small, take the best available.
    return f"bv*[height<={quality}]+ba/b[height<={quality}]/bv*+ba/b"


def make_workdir() -> Path:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="job_", dir=WORK_DIR))


def download(
    url: str,
    fmt: str,
    quality: str,
    on_progress: ProgressCallback | None = None,
) -> Download:
    """Download ``url`` and convert it to ``fmt``. Safe to call from worker threads."""
    workdir = make_workdir()
    try:
        return _download_into(url, fmt, quality, workdir, on_progress)
    except BaseException:
        shutil.rmtree(workdir, ignore_errors=True)
        raise


def _download_into(
    url: str,
    fmt: str,
    quality: str,
    workdir: Path,
    on_progress: ProgressCallback | None,
) -> Download:
    is_mp3 = fmt == FORMAT_MP3
    ext = "mp3" if is_mp3 else "mp4"

    options = _base_options()
    options.update(
        {
            "outtmpl": str(workdir / "item.%(ext)s"),
            "format": format_selector(fmt, quality),
            "progress_hooks": [_download_hook(on_progress)],
            "postprocessor_hooks": [_postprocess_hook(on_progress)],
        }
    )
    if is_mp3:
        options["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": quality}
        ]
    else:
        options["merge_output_format"] = "mp4"

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True) or {}

    output = workdir / f"item.{ext}"
    if not output.is_file():
        raise FileNotFoundError("No output file was produced by yt-dlp.")

    title = info.get("title") or "download"
    return Download(
        url=url,
        title=title,
        filename=f"{safe_name(title)}.{ext}",
        path=output,
        mime=MIME_TYPES[ext],
        workdir=workdir,
    )


def _base_options() -> dict:
    options: dict = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    cookies = cookies_path()
    if cookies:
        options["cookiefile"] = cookies
    return options


def _download_hook(on_progress: ProgressCallback | None):
    def hook(data: dict) -> None:
        if on_progress is None:
            return
        status = data.get("status")
        if status == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            downloaded = data.get("downloaded_bytes") or 0
            if total > 0:
                fraction = min(max(downloaded / total, 0.0), 1.0)
                on_progress(fraction, f"Downloading… {int(fraction * 100)}%")
            else:
                on_progress(None, "Downloading…")
        elif status == "finished":
            on_progress(1.0, "Download finished")

    return hook


def _postprocess_hook(on_progress: ProgressCallback | None):
    def hook(data: dict) -> None:
        if on_progress is None:
            return
        if data.get("status") == "started":
            on_progress(None, "Converting…")
        elif data.get("status") == "finished":
            on_progress(1.0, "Done")

    return hook


# ----------------------------------------------------------------------
# Files
# ----------------------------------------------------------------------
def safe_name(title: str, fallback: str = "download") -> str:
    """Turn a video title into a safe file name stem for Windows and other systems."""
    cleaned = sanitize_filename(title or "", restricted=False).strip()
    cleaned = cleaned[:MAX_STEM_LENGTH].rstrip(" .")
    if not cleaned:
        return fallback
    if cleaned.split(".")[0].upper() in _RESERVED_NAMES:
        cleaned = f"_{cleaned}"
    return cleaned


def unique_names(names: list[str]) -> list[str]:
    """Make names unique by appending ``_1``, ``_2`` ... before the extension."""
    used: set[str] = set()
    result: list[str] = []
    for name in names:
        stem, ext = os.path.splitext(name)
        candidate = name
        counter = 1
        while candidate in used:
            candidate = f"{stem}_{counter}{ext}"
            counter += 1
        used.add(candidate)
        result.append(candidate)
    return result


def build_zip(entries: list[tuple[str, Path]]) -> Path:
    """Store the given (file name, file path) pairs in a new ZIP and return its path.

    Media is already compressed, so the archive is stored without re-compressing.
    """
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="streamtune_", suffix=".zip", dir=WORK_DIR)
    os.close(fd)
    arcnames = unique_names([arcname for arcname, _ in entries])
    with zipfile.ZipFile(name, "w", zipfile.ZIP_STORED) as archive:
        for arcname, (_, path) in zip(arcnames, entries, strict=True):
            archive.write(path, arcname=arcname)
    return Path(name)


def discard_workdir(path: str | Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def remove_file(path: str | Path) -> None:
    try:
        Path(path).unlink()
    except OSError:
        pass


# ----------------------------------------------------------------------
# Errors and maintenance
# ----------------------------------------------------------------------
def explain_error(exc: BaseException) -> tuple[str, str]:
    """Return ``(friendly message, cleaned technical detail)`` for an exception."""
    detail = _ANSI_RE.sub("", str(exc)).strip()
    detail = _ERROR_PREFIX_RE.sub("", detail)
    lowered = detail.lower()
    for needles, message in _ERROR_HINTS:
        if any(needle in lowered for needle in needles):
            return message, detail
    return "Conversion failed.", detail


def update_ytdlp() -> tuple[bool, str]:
    """Upgrade yt-dlp with pip. The running process keeps the old version until restarted."""
    completed = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
        capture_output=True,
        text=True,
        timeout=600,
    )
    lines = [line for line in (completed.stdout + completed.stderr).splitlines() if line.strip()]
    last = lines[-1] if lines else "No output from pip."
    return completed.returncode == 0, last
