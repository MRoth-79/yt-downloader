"""Session state for StreamTune: defaults, restore after a refresh or restart, and saving.

The functions take the session as a plain mapping (``st.session_state`` in the app, a ``dict``
in tests), so this module does not import Streamlit.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from pathlib import Path

import downloader as dl

PERSISTED_KEYS = ("queue", "item_state", "results", "saved_items")


def default_state() -> dict:
    """Return fresh default values. Built on every call so sessions never share lists or dicts."""
    return {
        "queue": [],
        "item_state": {},
        "results": [],
        "draft_url_input": "",
        "clear_draft": False,
        "save_folder_name": "",
        "saved_items": {},
        "last_saved_dir": "",
        "ytdlp_job": None,
    }


def restore_session(data: Mapping) -> dict:
    """Rebuild the queue and finished downloads from data saved by an earlier run.

    Items that were still processing go back to pending, malformed or duplicate entries are
    dropped, and results whose files no longer exist are dropped.
    """
    saved_states = data.get("item_state") if isinstance(data.get("item_state"), dict) else {}
    queue: list[str] = []
    item_state: dict = {}
    for url in data.get("queue") or []:
        if not isinstance(url, str) or url in queue:
            continue
        state = saved_states.get(url)
        if not isinstance(state, dict):
            continue
        if state.get("status") == dl.STATUS_PROCESSING:
            state = {**state, "status": dl.STATUS_PENDING}
        queue.append(url)
        item_state[url] = state
    results = [
        item
        for item in data.get("results") or []
        if isinstance(item, dict) and Path(str(item.get("path", ""))).is_file()
    ]
    saved_items = data.get("saved_items") if isinstance(data.get("saved_items"), dict) else {}
    return {"queue": queue, "item_state": item_state, "results": results, "saved_items": saved_items}


def init_session_state(session: MutableMapping) -> None:
    """Fill in missing defaults, then restore the saved session once per browser session."""
    for key, value in default_state().items():
        if key not in session:
            session[key] = value
    if not session.get("restored"):
        for key, value in restore_session(dl.load_state()).items():
            session[key] = value
        session["restored"] = True


def session_snapshot(session: Mapping) -> dict:
    """Return the part of the session that is saved between runs."""
    return {key: session[key] for key in PERSISTED_KEYS}


def persist_session(session: Mapping) -> None:
    """Save the queue and finished downloads so a refresh or restart does not lose them."""
    dl.save_state(session_snapshot(session))
