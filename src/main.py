import hashlib
import html
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path

import streamlit as st
from yt_dlp.version import __version__ as YTDLP_VERSION

import downloader as dl

APP_UI_VERSION = "4.2.0"
MAX_PARALLEL = 2
STYLE_FILE = Path(__file__).resolve().with_name("styles.css")

STATUS_PENDING = dl.STATUS_PENDING
STATUS_PROCESSING = dl.STATUS_PROCESSING
STATUS_COMPLETED = dl.STATUS_COMPLETED
STATUS_ERROR = dl.STATUS_ERROR

st.set_page_config(
    page_title="StreamTune",
    page_icon=":material/graphic_eq:",
    layout="centered",
    initial_sidebar_state="collapsed",
)


@st.cache_resource(show_spinner="Setting up FFmpeg (first run only)...")
def get_ffmpeg_dir():
    return dl.ensure_ffmpeg()


@st.cache_resource
def remove_old_jobs() -> int:
    """Delete download folders left over from earlier runs. Runs once per server process."""
    return dl.cleanup_old_jobs(dl.JOB_MAX_AGE_HOURS)


def inject_styles():
    css = STYLE_FILE.read_text(encoding="utf-8")
    st.html(f"<style>{css}</style>")


def restore_session():
    """Load the queue and finished downloads saved by an earlier run (after a refresh or restart)."""
    data = dl.load_state()
    saved_states = data.get("item_state") if isinstance(data.get("item_state"), dict) else {}
    queue: list[str] = []
    item_state: dict = {}
    for url in data.get("queue") or []:
        if not isinstance(url, str) or url in queue:
            continue
        state = saved_states.get(url)
        if not isinstance(state, dict):
            continue
        if state.get("status") == STATUS_PROCESSING:
            state = {**state, "status": STATUS_PENDING}
        queue.append(url)
        item_state[url] = state
    results = [
        item
        for item in data.get("results") or []
        if isinstance(item, dict) and Path(str(item.get("path", ""))).is_file()
    ]
    saved_items = data.get("saved_items") if isinstance(data.get("saved_items"), dict) else {}
    st.session_state.queue = queue
    st.session_state.item_state = item_state
    st.session_state.results = results
    st.session_state.saved_items = saved_items


def init_session_state():
    defaults = {
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
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if not st.session_state.get("restored"):
        restore_session()
        st.session_state.restored = True


def persist_session():
    """Save the queue and finished downloads so a refresh or restart does not lose them."""
    dl.save_state(
        {
            "queue": st.session_state.queue,
            "item_state": st.session_state.item_state,
            "results": st.session_state.results,
            "saved_items": st.session_state.saved_items,
        }
    )


def digest(url: str) -> str:
    """Short, stable key suffix for widgets tied to a URL."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]


def format_choice(fmt: str) -> str:
    if fmt == dl.FORMAT_MP3:
        return ":material/audio_file: MP3"
    return ":material/movie: MP4"


# ----------------------------------------------------------------------
# Queue and result state
# ----------------------------------------------------------------------
def add_url(raw: str):
    """Check a link, read its details, and add it to the queue.

    Runs inside the script (not a callback) so a spinner can show while the link is read.
    """
    try:
        url = dl.validate_url(raw)
    except ValueError as exc:
        st.toast(str(exc), icon=":material/error:")
        return
    if url in st.session_state.queue:
        st.toast("That link is already in the queue.", icon=":material/info:")
        return
    with st.spinner("Reading link…"):
        try:
            info = dl.fetch_info(url)
        except ValueError as exc:
            st.toast(str(exc), icon=":material/error:")
            return
        except Exception as exc:
            message, _ = dl.explain_error(exc)
            st.toast(f"Could not read this link. {message}", icon=":material/error:")
            return

    notice = dl.playlist_notice(url)
    if notice:
        st.toast(notice, icon=":material/info:")
    st.session_state.queue.append(url)
    st.session_state.item_state[url] = {
        "status": STATUS_PENDING,
        "title": info["title"],
        "thumbnail": info["thumbnail"],
        "duration": info["duration"],
        "uploader": info["uploader"],
        "error": "",
        "detail": "",
        "options": None,
    }
    # The text box can only be cleared before it is drawn, so clear it on the next run.
    st.session_state.clear_draft = True
    persist_session()
    st.rerun()


def discard_result(url: str):
    kept = []
    for item in st.session_state.results:
        if item["url"] == url:
            dl.discard_workdir(item["workdir"])
        else:
            kept.append(item)
    st.session_state.results = kept


def remove_from_queue(url: str):
    if url in st.session_state.queue:
        st.session_state.queue.remove(url)
    st.session_state.item_state.pop(url, None)
    discard_result(url)


def save_results_to_folder():
    try:
        key = dl.clean_folder_name(st.session_state.save_folder_name)
    except ValueError as exc:
        st.toast(str(exc), icon=":material/error:")
        return
    already_saved = set(st.session_state.saved_items.get(key, []))
    new_items = [item for item in st.session_state.results if item["path"] not in already_saved]
    if not new_items:
        st.toast("Every finished file is already in this folder.", icon=":material/info:")
        return
    try:
        target = dl.save_to_folder(
            [(item["filename"], Path(item["path"])) for item in new_items],
            key,
        )
    except (ValueError, OSError) as exc:
        st.toast(f"Could not save the files: {exc}", icon=":material/error:")
        return
    st.session_state.saved_items[key] = sorted(already_saved | {item["path"] for item in new_items})
    st.session_state.last_saved_dir = str(target)
    st.toast(f"Saved {len(new_items)} new file(s).", icon=":material/check_circle:")


# ----------------------------------------------------------------------
# yt-dlp maintenance (runs in the background, shows progress)
# ----------------------------------------------------------------------
def start_ytdlp_update():
    proc, log_path = dl.start_ytdlp_update()
    st.session_state.ytdlp_job = {"proc": proc, "log": str(log_path), "shown": False}


def ytdlp_running() -> bool:
    job = st.session_state.ytdlp_job
    return job is not None and job["proc"].poll() is None


def update_panel():
    job = st.session_state.ytdlp_job
    running = ytdlp_running()
    if job is not None and not running and not job["shown"]:
        # The update just finished. Rerun the whole app once so polling stops and the result shows.
        job["shown"] = True
        st.rerun()
    if running:
        st.caption("Updating yt-dlp… this can take a minute.")
    elif job is not None:
        message = dl.ytdlp_update_message(Path(job["log"]))
        if job["proc"].returncode == 0:
            st.success(f"{message} Restart StreamTune to load the new version.")
        else:
            st.error(f"Update failed: {message}")
    st.button(
        "Update yt-dlp",
        key="update_ytdlp",
        icon=":material/system_update_alt:",
        on_click=start_ytdlp_update,
        disabled=running,
    )


def maintenance_panel():
    # Only poll while an update is running. Polling stops when the fragment is drawn without run_every.
    poll_every = 1 if ytdlp_running() else None
    st.fragment(run_every=poll_every)(update_panel)()


# ----------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------
def render_status_badge(status: str) -> str:
    labels = {
        STATUS_PENDING: ("Waiting", "pending"),
        STATUS_PROCESSING: ("Processing", "processing"),
        STATUS_COMPLETED: ("Completed", "completed"),
        STATUS_ERROR: ("Error", "error"),
    }
    text, css = labels.get(status, ("Unknown", "pending"))
    return f'<span class="status-badge {css}" aria-label="Status: {text}">{text}</span>'


def queue_card_html(url: str, state: dict, fmt: str, quality: str) -> str:
    status = state.get("status", STATUS_PENDING)
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


def render_queue(slot, fmt: str, quality: str, show_actions: bool):
    """Draw the queue into ``slot`` (an ``st.empty`` placeholder).

    Remove buttons are only drawn in the final render of a run, so that widget keys are unique.
    """
    queue = st.session_state.queue
    with slot.container(border=True):
        if not queue:
            st.markdown(
                """
                <div class="empty-queue" role="status">
                    <div class="empty-mark" aria-hidden="true"></div>
                    <p class="empty-title">Nothing queued yet</p>
                    <p class="empty-copy">Paste a media URL above, then choose Add to queue.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            return

        for url in queue:
            state = st.session_state.item_state.get(url, {})
            st.markdown(queue_card_html(url, state, fmt, quality), unsafe_allow_html=True)
            if state.get("status") == STATUS_ERROR and state.get("detail"):
                st.caption(f"Error detail: {state['detail'][:300]}")
            if show_actions:
                with st.container(horizontal=True, horizontal_alignment="right"):
                    st.button(
                        "Remove",
                        key=f"rm_{digest(url)}",
                        on_click=remove_from_queue,
                        args=(url,),
                        icon=":material/delete:",
                        help="Remove this item from the queue",
                    )


def run_conversions(urls: list[str], fmt: str, quality: str, queue_slot) -> int:
    """Convert ``urls`` in parallel and show per-item progress. Returns the number of successes."""
    progress: dict[str, tuple[float | None, str]] = {}

    def writer(url: str):
        def report(fraction, text):
            progress[url] = (fraction, text)

        return report

    futures = {}
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
        for url in urls:
            state = st.session_state.item_state[url]
            state.update(status=STATUS_PROCESSING, error="", detail="")
            futures[url] = pool.submit(dl.download, url, fmt, quality, writer(url))

        slots = {url: st.empty() for url in urls}
        render_queue(queue_slot, fmt, quality, show_actions=False)

        while True:
            _, not_done = wait(list(futures.values()), timeout=0.25)
            for url in urls:
                if futures[url].done():
                    continue
                fraction, text = progress.get(url, (0.0, "Starting…"))
                title = st.session_state.item_state[url].get("title") or url
                slots[url].progress(fraction or 0.0, text=f"{title}: {text}")
            if not not_done:
                break

    successes = 0
    for url in urls:
        state = st.session_state.item_state[url]
        slot = slots[url]
        try:
            result = futures[url].result()
        except Exception as exc:
            friendly, detail = dl.explain_error(exc)
            state.update(status=STATUS_ERROR, error=friendly, detail=detail)
            slot.error(f"{state.get('title') or url}: {friendly}", icon=":material/error:")
            continue

        successes += 1
        state.update(
            status=STATUS_COMPLETED,
            title=result.title,
            error="",
            detail="",
            options=(fmt, quality),
        )
        discard_result(url)
        st.session_state.results.append(
            {
                "url": url,
                "title": result.title,
                "filename": result.filename,
                "path": str(result.path),
                "mime": result.mime,
                "workdir": str(result.workdir),
            }
        )
        slot.success(f"Completed: {result.title}", icon=":material/check_circle:")

    return successes


# ----------------------------------------------------------------------
# App
# ----------------------------------------------------------------------
inject_styles()
remove_old_jobs()
init_session_state()

ffmpeg_ok = get_ffmpeg_dir() is not None
ffmpeg_label = "FFmpeg ready" if ffmpeg_ok else "FFmpeg unavailable"
ffmpeg_class = "ok" if ffmpeg_ok else "bad"
queue_len = len(st.session_state.queue)

st.markdown(
    f"""
    <header class="app-topbar">
        <div class="brand">
            <span class="brand-glyph" aria-hidden="true"><span></span><span></span><span></span></span>
            <div>
                <div class="brand-name">StreamTune</div>
                <div class="brand-version">Version {APP_UI_VERSION}</div>
            </div>
        </div>
        <span class="sys-pill {ffmpeg_class}" role="status" aria-live="polite">
            <span class="sys-mark" aria-hidden="true"></span>
            {ffmpeg_label}
        </span>
    </header>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <section class="hero-card">
        <h1 class="hero-title">Convert authorized media</h1>
        <p class="hero-lead">
            Add a URL you may use, choose MP3 or MP4, then convert the queue and save the files.
        </p>
        <ol class="flow" aria-label="Process">
            <li><span class="flow-index">1</span> Source</li>
            <li><span class="flow-index">2</span> Format</li>
            <li><span class="flow-index">3</span> Queue</li>
            <li><span class="flow-index">4</span> Convert</li>
        </ol>
    </section>
    """,
    unsafe_allow_html=True,
)

st.markdown('<h2 class="section-title">Add a source</h2>', unsafe_allow_html=True)
with st.container(border=True, key="source_card"):
    if st.session_state.clear_draft:
        st.session_state.draft_url_input = ""
        st.session_state.clear_draft = False
    st.markdown(
        """
        <p class="helper-text">
            Paste a URL for media you are authorized to convert
            (content you own, have licensed, or may legally access).
        </p>
        """,
        unsafe_allow_html=True,
    )
    st.text_input(
        "Media URL",
        key="draft_url_input",
        placeholder="https://",
        help="Only add sources you have permission to convert.",
    )
    st.caption("One authorized URL per queue item. The title and preview are read when you add it.")
    if st.button(
        "Add to queue",
        type="secondary",
        width="stretch",
        icon=":material/playlist_add:",
        key="add_to_queue",
        help="Checks the URL and adds it to the conversion queue",
    ):
        add_url(st.session_state.draft_url_input)

st.space("small")
with st.container(border=True, key="format_card"):
    format_type = st.radio(
        "Output format",
        [dl.FORMAT_MP3, dl.FORMAT_MP4],
        index=0,
        horizontal=True,
        width="stretch",
        key="output_format",
        format_func=format_choice,
        captions=[
            "Audio only, smaller files, ideal for music or podcasts.",
            "Video with audio, best when you need the full picture.",
        ],
        help="Applies to every item in this conversion.",
    )
    if format_type == dl.FORMAT_MP3:
        quality = st.selectbox(
            "MP3 bitrate",
            options=list(dl.MP3_BITRATES),
            format_func=dl.MP3_BITRATES.get,
            key="mp3_bitrate",
            help="Higher bitrate means better audio and larger files.",
        )
    else:
        quality = st.selectbox(
            "Maximum resolution",
            options=list(dl.MP4_HEIGHTS),
            format_func=dl.MP4_HEIGHTS.get,
            key="mp4_height",
            help="Uses the best available video up to this resolution.",
        )

st.space("small")
queue_count = f'<span class="section-count">{queue_len}</span>' if queue_len else ""
st.markdown(f'<h2 class="section-title">Queue{queue_count}</h2>', unsafe_allow_html=True)
queue_slot = st.empty()  # filled below, after any conversion has updated the item states

can_convert = queue_len > 0 and ffmpeg_ok

st.space("small")
st.markdown('<h2 class="section-title">Convert</h2>', unsafe_allow_html=True)
if not ffmpeg_ok:
    st.warning(
        "FFmpeg is not available. Install dependencies or restart the app before converting.",
        icon=":material/error:",
    )

if queue_len == 0:
    st.markdown(
        '<p class="helper-text" role="status" aria-live="polite">'
        "Start conversion is disabled until you add at least one authorized item to the queue."
        "</p>",
        unsafe_allow_html=True,
    )
elif not ffmpeg_ok:
    st.markdown(
        '<p class="helper-text" role="status" aria-live="polite">'
        "Start conversion is disabled until FFmpeg is ready."
        "</p>",
        unsafe_allow_html=True,
    )

if st.button(
    "Start conversion",
    type="primary",
    disabled=not can_convert,
    width="stretch",
    icon=":material/play_arrow:",
    key="start_conversion",
    help="Convert queued items that are not done yet. Failed items are retried.",
):
    pending = [
        url
        for url in st.session_state.queue
        if dl.needs_conversion(st.session_state.item_state.get(url), format_type, quality)
    ]
    if not pending:
        st.info("Everything in the queue is already converted with these settings.")
    else:
        successes = run_conversions(pending, format_type, quality, queue_slot)
        if successes:
            st.balloons()

# Final queue render (with Remove buttons). Replaces the progress view if conversion ran.
render_queue(queue_slot, format_type, quality, show_actions=True)

if st.session_state.results:
    st.markdown('<h2 class="section-title">Downloads</h2>', unsafe_allow_html=True)
    with st.container(border=True, key="save_card"):
        st.text_input(
            "Save to folder",
            key="save_folder_name",
            placeholder="e.g. Road trip mix",
            help=f"Creates this folder in {dl.SAVE_ROOT} and saves every finished file into it.",
        )
        st.button(
            "Save all to folder",
            type="secondary",
            width="stretch",
            on_click=save_results_to_folder,
            icon=":material/create_new_folder:",
            key="save_to_folder",
        )
        if st.session_state.last_saved_dir:
            st.caption(f"Saved to {st.session_state.last_saved_dir}")
    # The data callable runs only when the user clicks, so files are not read on every rerun.
    for item in st.session_state.results:
        path = Path(item["path"])
        st.download_button(
            label=f"Download {item['filename']}",
            data=lambda p=path: p.read_bytes(),
            file_name=item["filename"],
            mime=item["mime"],
            key=f"saved_dl_{digest(item['url'])}",
            icon=":material/download:",
            type="secondary",
            width="stretch",
            on_click="ignore",
        )

if len(st.session_state.results) > 1:
    st.space("small")
    entries = [(item["filename"], Path(item["path"])) for item in st.session_state.results]
    st.download_button(
        label=f"Download all as ZIP ({len(entries)} files)",
        data=lambda e=entries: dl.zip_bytes(e),
        file_name="streamtune_downloads.zip",
        mime="application/zip",
        icon=":material/folder_zip:",
        type="primary",
        width="stretch",
        key="zip_download",
        on_click="ignore",
    )

st.space("small")
with st.expander("Maintenance"):
    st.caption(
        f"yt-dlp version {YTDLP_VERSION}. Sites change often, so update it when downloads start failing."
    )
    st.caption(
        "Updating runs pip and changes the Python environment StreamTune runs in (usually the "
        f"project's .venv), within the tested range {dl.YTDLP_REQUIREMENT}. "
        "Restart StreamTune afterwards to load the new version."
    )
    maintenance_panel()

persist_session()
