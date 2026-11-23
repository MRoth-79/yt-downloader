from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import downloader as dl

MAIN = Path(__file__).resolve().parent.parent / "src" / "main.py"
PLAYLIST_URL = "https://example.com/playlist?list=abc"
ENTRY_URLS = [f"https://example.com/watch?v={i}" for i in range(1, 4)]


def _playlist(urls=ENTRY_URLS, total=None):
    return {
        "type": "playlist",
        "title": "Mix",
        "total": total or len(urls),
        "entries": [
            {"url": url, "title": f"Song {i}", "thumbnail": "", "duration": 60 + i, "uploader": "Band"}
            for i, url in enumerate(urls, start=1)
        ],
    }


@pytest.fixture
def app(tmp_path, monkeypatch):
    """The real Streamlit app with no network access and a throwaway session file."""
    monkeypatch.setattr(dl, "WORK_DIR", tmp_path)
    monkeypatch.setattr(dl, "STATE_FILE", tmp_path / "session.json")
    monkeypatch.setattr(dl, "ensure_ffmpeg", lambda: str(tmp_path))
    at = AppTest.from_file(str(MAIN), default_timeout=30)
    at.run()
    assert not at.exception
    return at


def _add(at, url):
    at.text_input(key="draft_url_input").input(url)
    at.button(key="add_to_queue").click().run()
    assert not at.exception


def _toasts(at):
    return [toast.value for toast in at.toast]


def test_add_url_enqueues_every_playlist_entry(app, monkeypatch):
    seen = []
    monkeypatch.setattr(dl, "fetch_info", lambda url: seen.append(url) or _playlist())

    _add(app, PLAYLIST_URL)

    assert seen == [PLAYLIST_URL]
    assert app.session_state["queue"] == ENTRY_URLS
    states = app.session_state["item_state"]
    assert [states[url]["title"] for url in ENTRY_URLS] == ["Song 1", "Song 2", "Song 3"]
    assert {states[url]["status"] for url in ENTRY_URLS} == {dl.STATUS_PENDING}
    assert _toasts(app) == ["Added 3 items from “Mix”."]
    assert dl.load_state()["queue"] == ENTRY_URLS
    assert app.text_input(key="draft_url_input").value == ""


def test_add_url_skips_playlist_entries_already_queued(app, monkeypatch):
    monkeypatch.setattr(dl, "fetch_info", lambda url: _playlist(ENTRY_URLS[:1]))
    _add(app, PLAYLIST_URL)

    monkeypatch.setattr(dl, "fetch_info", lambda url: _playlist(total=450))
    _add(app, PLAYLIST_URL)

    assert app.session_state["queue"] == ENTRY_URLS
    assert _toasts(app) == [
        "Added 2 items from “Mix”. 1 item already in the queue was skipped. "
        f"Only the first {dl.MAX_PLAYLIST_ITEMS} of 450 items were read."
    ]

    monkeypatch.setattr(dl, "fetch_info", lambda url: _playlist())
    _add(app, PLAYLIST_URL)

    assert app.session_state["queue"] == ENTRY_URLS
    assert _toasts(app) == ["Every item from “Mix” is already in the queue."]


def test_add_url_single_video_behaviour_is_unchanged(app, monkeypatch):
    info = {"title": "Song", "thumbnail": "https://img/1.jpg", "duration": 65, "uploader": "Band"}
    monkeypatch.setattr(dl, "fetch_info", lambda url: dict(info))
    url = "https://example.com/watch?v=9&list=abc"

    _add(app, url)

    assert app.session_state["queue"] == [url]
    assert app.session_state["item_state"][url] == {
        **info,
        "status": dl.STATUS_PENDING,
        "error": "",
        "detail": "",
        "options": None,
    }
    assert _toasts(app) == [dl.playlist_notice(url)]

    _add(app, url)

    assert app.session_state["queue"] == [url]
    assert _toasts(app) == ["That link is already in the queue."]
