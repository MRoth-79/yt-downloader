import pytest

import downloader as dl
import ui


@pytest.mark.parametrize(
    "added, duplicates, total, expected",
    [
        (3, 0, 3, "Added 3 items from “Mix”."),
        (1, 0, 1, "Added 1 item from “Mix”."),
        (2, 1, 3, "Added 2 items from “Mix”. 1 item already in the queue was skipped."),
        (1, 2, 3, "Added 1 item from “Mix”. 2 items already in the queue were skipped."),
        (0, 3, 3, "Every item from “Mix” is already in the queue."),
        (200, 0, 500, "Added 200 items from “Mix”. Only the first 200 of 500 items were read."),
    ],
)
def test_playlist_message(added, duplicates, total, expected):
    assert ui.playlist_message("Mix", added, duplicates, total, limit=200) == expected


def test_playlist_message_without_title():
    assert ui.playlist_message("", 2, 0, 2) == "Added 2 items from the playlist."


@pytest.mark.parametrize(
    "status, text, css",
    [
        (dl.STATUS_PENDING, "Waiting", "pending"),
        (dl.STATUS_PROCESSING, "Processing", "processing"),
        (dl.STATUS_COMPLETED, "Completed", "completed"),
        (dl.STATUS_ERROR, "Error", "error"),
        ("something else", "Unknown", "pending"),
    ],
)
def test_render_status_badge(status, text, css):
    badge = ui.render_status_badge(status)
    assert f'class="status-badge {css}"' in badge
    assert f'aria-label="Status: {text}">{text}</span>' in badge


def test_queue_card_html_escapes_title_url_and_thumbnail():
    state = {
        "status": dl.STATUS_ERROR,
        "title": "<script>alert(1)</script>",
        "thumbnail": 'https://img/x.jpg"onerror="x',
    }
    card = ui.queue_card_html("https://example.com/?a=1&b=<2>", state, dl.FORMAT_MP3, "192")

    assert "<script>" not in card
    assert "&lt;script&gt;" in card
    assert 'x.jpg&quot;onerror=&quot;x"' in card
    assert "a=1&amp;b=&lt;2&gt;" in card
    assert 'class="queue-card is-error"' in card


def test_queue_card_html_falls_back_to_url_and_omits_optional_parts():
    card = ui.queue_card_html("https://example.com/a", {}, dl.FORMAT_MP4, "720")

    assert '<h3 class="queue-card-title">https://example.com/a</h3>' in card
    assert "queue-thumb" not in card
    assert "<dt>Length</dt>" not in card
    assert f"MP4 · {dl.MP4_HEIGHTS['720']}" in card
    assert 'class="queue-card is-pending"' in card


def test_queue_card_html_prefers_options_the_item_was_converted_with():
    state = {"status": dl.STATUS_COMPLETED, "options": ["MP3", "320"], "duration": 65}
    card = ui.queue_card_html("https://example.com/a", state, dl.FORMAT_MP4, "best")

    assert f"MP3 · {dl.MP3_BITRATES['320']}" in card
    assert "<dt>Length</dt><dd>1:05</dd>" in card
