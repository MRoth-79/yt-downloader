import downloader as dl
import state


def _item(status=dl.STATUS_PENDING, **extra):
    return {"status": status, "title": "Song", **extra}


# ----------------------------------------------------------------------
# restore_session
# ----------------------------------------------------------------------
def test_restore_session_turns_processing_items_back_into_pending():
    data = {
        "queue": ["https://a", "https://b"],
        "item_state": {
            "https://a": _item(dl.STATUS_PROCESSING),
            "https://b": _item(dl.STATUS_COMPLETED),
        },
    }

    restored = state.restore_session(data)

    assert restored["item_state"]["https://a"]["status"] == dl.STATUS_PENDING
    assert restored["item_state"]["https://b"]["status"] == dl.STATUS_COMPLETED
    assert data["item_state"]["https://a"]["status"] == dl.STATUS_PROCESSING


def test_restore_session_drops_duplicates_and_malformed_entries():
    data = {
        "queue": ["https://a", "https://a", 42, "https://missing", "https://bad"],
        "item_state": {"https://a": _item(), "https://bad": "not a dict"},
    }

    restored = state.restore_session(data)

    assert restored["queue"] == ["https://a"]
    assert list(restored["item_state"]) == ["https://a"]


def test_restore_session_keeps_only_results_whose_files_exist(tmp_path):
    kept = tmp_path / "kept.mp3"
    kept.write_bytes(b"x")
    data = {
        "results": [
            {"url": "https://a", "path": str(kept)},
            {"url": "https://b", "path": str(tmp_path / "gone.mp3")},
            "not a dict",
        ]
    }

    assert state.restore_session(data)["results"] == [{"url": "https://a", "path": str(kept)}]


def test_restore_session_handles_empty_or_wrongly_typed_data():
    expected = {"queue": [], "item_state": {}, "results": [], "saved_items": {}}
    assert state.restore_session({}) == expected
    assert state.restore_session({"item_state": [], "saved_items": "x", "queue": None}) == expected


# ----------------------------------------------------------------------
# defaults, init, snapshot, persist
# ----------------------------------------------------------------------
def test_default_state_returns_fresh_containers():
    first = state.default_state()
    second = state.default_state()
    first["queue"].append("https://a")
    assert second["queue"] == []


def test_init_session_state_fills_defaults_and_restores_once(monkeypatch):
    saved = {"queue": ["https://a"], "item_state": {"https://a": _item(dl.STATUS_PROCESSING)}}
    calls = []
    monkeypatch.setattr(dl, "load_state", lambda: calls.append(1) or saved)
    session = {"draft_url_input": "kept"}

    state.init_session_state(session)
    state.init_session_state(session)

    assert calls == [1]
    assert session["restored"] is True
    assert session["draft_url_input"] == "kept"
    assert session["queue"] == ["https://a"]
    assert session["item_state"]["https://a"]["status"] == dl.STATUS_PENDING
    assert session["ytdlp_job"] is None


def test_session_snapshot_keeps_only_persisted_keys():
    session = {**state.default_state(), "queue": ["https://a"], "restored": True}
    snapshot = state.session_snapshot(session)
    assert set(snapshot) == set(state.PERSISTED_KEYS)
    assert snapshot["queue"] == ["https://a"]


def test_persist_then_restore_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "WORK_DIR", tmp_path)
    monkeypatch.setattr(dl, "STATE_FILE", tmp_path / "session.json")
    session = state.default_state()
    session["queue"] = ["https://a"]
    session["item_state"] = {"https://a": _item(dl.STATUS_PROCESSING)}

    state.persist_session(session)
    restored = state.restore_session(dl.load_state())

    assert restored["queue"] == ["https://a"]
    assert restored["item_state"]["https://a"]["status"] == dl.STATUS_PENDING
