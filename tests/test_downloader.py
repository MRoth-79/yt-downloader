import io
import os
import time
import zipfile

import pytest

import downloader as dl


# ----------------------------------------------------------------------
# validate_url
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("https://example.com/watch?v=1", "https://example.com/watch?v=1"),
        ("  http://example.com/a  ", "http://example.com/a"),
    ],
)
def test_validate_url_accepts_http_urls(raw, expected):
    assert dl.validate_url(raw) == expected


@pytest.mark.parametrize(
    "raw", ["", "   ", None, "ftp://example.com/a", "example.com/a", "https://", "javascript:alert(1)"]
)
def test_validate_url_rejects_bad_input(raw):
    with pytest.raises(ValueError):
        dl.validate_url(raw)


# ----------------------------------------------------------------------
# safe_name
# ----------------------------------------------------------------------
def test_safe_name_removes_illegal_characters():
    name = dl.safe_name('My <video>: "best" / cut?')
    for char in '<>:"/\\|?*':
        assert char not in name


def test_safe_name_keeps_unicode_titles():
    assert dl.safe_name("שיר חדש 2026") == "שיר חדש 2026"


def test_safe_name_prefixes_reserved_windows_names():
    assert dl.safe_name("CON") == "_CON"
    assert dl.safe_name("nul.txt") == "_nul.txt"
    assert dl.safe_name("com3") == "_com3"


def test_safe_name_falls_back_when_empty():
    assert dl.safe_name("   ", fallback="download_2") == "download_2"
    assert dl.safe_name("...") == "download"


def test_safe_name_limits_length():
    assert len(dl.safe_name("a" * 500)) <= dl.MAX_STEM_LENGTH


# ----------------------------------------------------------------------
# unique_names and build_zip
# ----------------------------------------------------------------------
def test_unique_names_adds_counters_without_collisions():
    assert dl.unique_names(["a.mp3", "a.mp3", "a_1.mp3", "a.mp3"]) == [
        "a.mp3",
        "a_1.mp3",
        "a_1_1.mp3",
        "a_2.mp3",
    ]


def test_build_zip_contains_all_files(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "WORK_DIR", tmp_path / "work")
    first = tmp_path / "one.mp3"
    second = tmp_path / "two.mp3"
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    zip_path = dl.build_zip([("song.mp3", first), ("song.mp3", second)])

    with zipfile.ZipFile(zip_path) as archive:
        assert sorted(archive.namelist()) == ["song.mp3", "song_1.mp3"]
        assert archive.read("song.mp3") == b"first"
        assert archive.read("song_1.mp3") == b"second"


def test_clean_folder_name_replaces_separators_and_illegal_characters():
    assert dl.clean_folder_name("My <mix>: 1/2") == "My _mix__ 1_2"
    assert dl.clean_folder_name("..\\..\\evil") == ".._.._evil"


def test_clean_folder_name_rejects_empty_names():
    with pytest.raises(ValueError):
        dl.clean_folder_name("   ")
    with pytest.raises(ValueError):
        dl.clean_folder_name("...")


def test_clean_folder_name_prefixes_reserved_names():
    assert dl.clean_folder_name("CON") == "_CON"


def test_save_to_folder_copies_files_into_named_folder(tmp_path):
    first = tmp_path / "one.mp3"
    second = tmp_path / "two.mp3"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    root = tmp_path / "saved"

    target = dl.save_to_folder([("song.mp3", first), ("song.mp3", second)], "Road trip", root=root)

    assert target == root / "Road trip"
    assert sorted(p.name for p in target.iterdir()) == ["song.mp3", "song_1.mp3"]
    assert (target / "song.mp3").read_bytes() == b"first"
    assert (target / "song_1.mp3").read_bytes() == b"second"


def test_save_to_folder_never_overwrites_existing_files(tmp_path):
    source = tmp_path / "one.mp3"
    source.write_bytes(b"new")
    root = tmp_path / "saved"
    dl.save_to_folder([("song.mp3", source)], "mix", root=root)

    dl.save_to_folder([("song.mp3", source)], "mix", root=root)

    assert sorted(p.name for p in (root / "mix").iterdir()) == ["song.mp3", "song_1.mp3"]


def test_save_to_folder_requires_entries_and_name(tmp_path):
    source = tmp_path / "one.mp3"
    source.write_bytes(b"x")
    with pytest.raises(ValueError):
        dl.save_to_folder([], "mix", root=tmp_path)
    with pytest.raises(ValueError):
        dl.save_to_folder([("song.mp3", source)], "  ", root=tmp_path)


# ----------------------------------------------------------------------
# format selection and labels
# ----------------------------------------------------------------------
def test_format_selector_for_mp3_ignores_video_quality():
    assert dl.format_selector(dl.FORMAT_MP3, "320") == "bestaudio/best"


def test_format_selector_best_mp4():
    assert dl.format_selector(dl.FORMAT_MP4, "best") == "bv*+ba/b"


def test_format_selector_mp4_limits_height_with_fallback():
    selector = dl.format_selector(dl.FORMAT_MP4, "720")
    assert "height<=720" in selector
    assert selector.endswith("bv*+ba/b")


def test_quality_label_uses_table_labels():
    assert dl.quality_label(dl.FORMAT_MP3, "320") == dl.MP3_BITRATES["320"]
    assert dl.quality_label(dl.FORMAT_MP4, "1080") == dl.MP4_HEIGHTS["1080"]


@pytest.mark.parametrize("seconds, expected", [(0, ""), (None, ""), (65, "1:05"), (3725, "1:02:05")])
def test_format_duration(seconds, expected):
    assert dl.format_duration(seconds) == expected


# ----------------------------------------------------------------------
# error explanations
# ----------------------------------------------------------------------
def test_explain_error_strips_ansi_and_prefix():
    message, detail = dl.explain_error(RuntimeError("\x1b[0;31mERROR:\x1b[0m [youtube] abc: Something odd"))
    assert message == "Conversion failed."
    assert detail == "[youtube] abc: Something odd"
    assert "\x1b" not in detail


@pytest.mark.parametrize(
    "text, expected_fragment",
    [
        ("ERROR: [youtube] x: Private video. Sign in if...", "private"),
        ("Sign in to confirm you're not a bot", "sign-in"),
        ("The uploader has not made this video available in your country", "region"),
        ("Video unavailable", "unavailable"),
        ("HTTP Error 429: Too Many Requests", "rate-limiting"),
        ("Unsupported URL: https://x", "not supported"),
    ],
)
def test_explain_error_maps_common_failures(text, expected_fragment):
    message, _ = dl.explain_error(RuntimeError(text))
    assert expected_fragment in message.lower()


# ----------------------------------------------------------------------
# needs_conversion, zip_bytes, playlist handling
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "state, expected",
    [
        (None, True),
        ({}, True),
        ({"status": dl.STATUS_PENDING}, True),
        ({"status": dl.STATUS_ERROR, "options": ["MP3", "192"]}, True),
        ({"status": dl.STATUS_COMPLETED, "options": ["MP3", "192"]}, False),
        ({"status": dl.STATUS_COMPLETED, "options": ["MP3", "320"]}, True),
    ],
)
def test_needs_conversion(state, expected):
    assert dl.needs_conversion(state, dl.FORMAT_MP3, "192") is expected


def test_zip_bytes_returns_archive_and_removes_temp_file(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "WORK_DIR", tmp_path / "work")
    source = tmp_path / "one.mp3"
    source.write_bytes(b"data")

    payload = dl.zip_bytes([("song.mp3", source)])

    assert zipfile.ZipFile(io.BytesIO(payload)).read("song.mp3") == b"data"
    assert list((tmp_path / "work").glob("streamtune_*.zip")) == []


def test_playlist_notice_only_for_video_inside_playlist():
    assert "playlist is ignored" in dl.playlist_notice("https://example.com/watch?v=1&list=abc")
    assert dl.playlist_notice("https://example.com/watch?v=1") == ""
    assert dl.playlist_notice("https://example.com/playlist?list=abc") == ""


def test_fetch_info_rejects_playlists(monkeypatch):
    class FakeYDL:
        def __init__(self, options):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download):
            return {"_type": "playlist", "title": "A list", "entries": []}

    monkeypatch.setattr(dl.yt_dlp, "YoutubeDL", FakeYDL)
    with pytest.raises(ValueError, match="Playlist"):
        dl.fetch_info("https://example.com/playlist?list=abc")


# ----------------------------------------------------------------------
# temp cleanup, saved session, yt-dlp update log
# ----------------------------------------------------------------------
def test_cleanup_old_jobs_removes_only_old_job_folders(tmp_path, monkeypatch):
    work = tmp_path / "work"
    monkeypatch.setattr(dl, "WORK_DIR", work)
    old = work / "job_old"
    fresh = work / "job_fresh"
    other = work / "keep_me"
    for folder in (old, fresh, other):
        folder.mkdir(parents=True)
    three_days_ago = time.time() - 3 * 24 * 3600
    os.utime(old, (three_days_ago, three_days_ago))
    os.utime(other, (three_days_ago, three_days_ago))

    assert dl.cleanup_old_jobs(24) == 1
    assert not old.exists()
    assert fresh.exists()
    assert other.exists()


def test_cleanup_old_jobs_handles_missing_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "WORK_DIR", tmp_path / "missing")
    assert dl.cleanup_old_jobs(24) == 0


def test_state_round_trip_and_bad_file(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "WORK_DIR", tmp_path)
    monkeypatch.setattr(dl, "STATE_FILE", tmp_path / "session.json")

    assert dl.load_state() == {}
    dl.save_state({"queue": ["https://example.com/a"], "item_state": {}})
    assert dl.load_state() == {"queue": ["https://example.com/a"], "item_state": {}}

    (tmp_path / "session.json").write_text("not json", encoding="utf-8")
    assert dl.load_state() == {}


def test_ytdlp_requirement_matches_requirements_file():
    requirements = (dl.PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    pins = [line.strip() for line in requirements if line.strip().startswith("yt-dlp")]
    assert pins == [dl.YTDLP_REQUIREMENT]
    assert "<" in dl.YTDLP_REQUIREMENT


def test_start_ytdlp_update_uses_bounded_requirement(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "WORK_DIR", tmp_path)
    monkeypatch.setattr(dl, "YTDLP_LOG_FILE", tmp_path / "update.log")
    calls = []
    monkeypatch.setattr(dl.subprocess, "Popen", lambda args, **kwargs: calls.append(args) or "proc")

    proc, log_path = dl.start_ytdlp_update()

    assert proc == "proc"
    assert log_path == tmp_path / "update.log"
    assert calls[0][-1] == dl.YTDLP_REQUIREMENT
    assert "yt-dlp" not in calls[0][:-1]


def test_ytdlp_update_message_uses_last_line(tmp_path):
    log = tmp_path / "log.txt"
    log.write_text("Collecting yt-dlp\n\nSuccessfully installed yt-dlp-2026.1\n", encoding="utf-8")
    assert dl.ytdlp_update_message(log) == "Successfully installed yt-dlp-2026.1"
    assert dl.ytdlp_update_message(tmp_path / "missing.txt") == "No output from pip."
