import pytest

import downloader as dl
import ui


def test_digest_is_short_stable_and_url_specific():
    first = ui.digest("https://example.com/a")
    assert first == ui.digest("https://example.com/a")
    assert first != ui.digest("https://example.com/b")
    assert len(first) == 12


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
