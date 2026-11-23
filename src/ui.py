"""Queue rendering for StreamTune: HTML helpers and the Streamlit queue view."""

from __future__ import annotations

import html
from collections.abc import Callable

import streamlit as st

import downloader as dl
from state import digest

EMPTY_QUEUE_HTML = """
<div class="empty-queue" role="status">
    <div class="empty-mark" aria-hidden="true"></div>
    <p class="empty-title">Nothing queued yet</p>
    <p class="empty-copy">Paste a media URL above, then choose Add to queue.</p>
</div>
"""


def _items(count: int) -> str:
    return f"{count} item" if count == 1 else f"{count} items"


def playlist_message(
    title: str, added: int, duplicates: int, total: int, limit: int = dl.MAX_PLAYLIST_ITEMS
) -> str:
    """Toast text after a playlist link was read and its items were queued."""
    name = f"“{title}”" if title else "the playlist"
    if added:
        parts = [f"Added {_items(added)} from {name}."]
    else:
        parts = [f"Every item from {name} is already in the queue."]
    if added and duplicates:
        verb = "was" if duplicates == 1 else "were"
        parts.append(f"{_items(duplicates)} already in the queue {verb} skipped.")
    if total > limit:
        parts.append(f"Only the first {limit} of {total} items were read.")
    return " ".join(parts)


def render_status_badge(status: str) -> str:
    labels = {
        dl.STATUS_PENDING: ("Waiting", "pending"),
        dl.STATUS_PROCESSING: ("Processing", "processing"),
        dl.STATUS_COMPLETED: ("Completed", "completed"),
        dl.STATUS_ERROR: ("Error", "error"),
    }
    text, css = labels.get(status, ("Unknown", "pending"))
    return f'<span class="status-badge {css}" aria-label="Status: {text}">{text}</span>'


def queue_card_html(url: str, state: dict, fmt: str, quality: str) -> str:
    status = state.get("status", dl.STATUS_PENDING)
    title = html.escape(state.get("title") or url)
    thumbnail = state.get("thumbnail") or ""
    thumb_html = (
        f'<img class="queue-thumb" src="{html.escape(thumbnail)}" alt="" loading="lazy" '
        'referrerpolicy="no-referrer">'
        if thumbnail
        else ""
    )
    opt_fmt, opt_quality = state.get("options") or (fmt, quality)
    format_text = f"{opt_fmt} · {dl.quality_label(opt_fmt, opt_quality)}"
    rows = [("Source", url), ("Format", format_text)]
    duration = dl.format_duration(state.get("duration"))
    if duration:
        rows.append(("Length", duration))
    meta = "".join(f"<div><dt>{label}</dt><dd>{html.escape(value)}</dd></div>" for label, value in rows)
    return (
        f'<article class="queue-card is-{status}">'
        f'<div class="queue-row">{thumb_html}'
        f'<div class="queue-main">'
        f'<div class="queue-head"><h3 class="queue-card-title">{title}</h3>'
        f"{render_status_badge(status)}</div>"
        f'<dl class="queue-meta">{meta}</dl>'
        "</div></div></article>"
    )


def render_queue(
    slot,
    queue: list[str],
    item_state: dict,
    fmt: str,
    quality: str,
    on_remove: Callable[[str], None] | None = None,
):
    """Draw the queue into ``slot`` (an ``st.empty`` placeholder).

    Remove buttons are drawn only when ``on_remove`` is given. Pass it only in the final render
    of a run, so that widget keys are unique.
    """
    with slot.container(border=True):
        if not queue:
            st.markdown(EMPTY_QUEUE_HTML, unsafe_allow_html=True)
            return

        for url in queue:
            state = item_state.get(url, {})
            st.markdown(queue_card_html(url, state, fmt, quality), unsafe_allow_html=True)
            if state.get("status") == dl.STATUS_ERROR and state.get("detail"):
                st.caption(f"Error detail: {state['detail'][:300]}")
            if on_remove is not None:
                with st.container(horizontal=True, horizontal_alignment="right"):
                    st.button(
                        "Remove",
                        key=f"rm_{digest(url)}",
                        on_click=on_remove,
                        args=(url,),
                        icon=":material/delete:",
                        help="Remove this item from the queue",
                    )
