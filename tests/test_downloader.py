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
