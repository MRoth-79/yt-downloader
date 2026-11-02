import os
import io
import sys
import html
import shutil
import zipfile
import tempfile
import subprocess
import importlib
from pathlib import Path

import streamlit as st

APP_UI_VERSION = "4.1"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

FORMAT_MP3 = "MP3"
FORMAT_MP4 = "MP4"
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_ERROR = "error"


def ensure_package(module_name, pip_name=None):
    try:
        return importlib.import_module(module_name)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name or module_name])
        return importlib.import_module(module_name)


@st.cache_resource(show_spinner="Setting up FFmpeg (first run only)...")
def setup_ffmpeg():
    existing = shutil.which("ffmpeg")
    if existing:
        return os.path.dirname(existing)
    static_ffmpeg = ensure_package("static_ffmpeg", "static-ffmpeg")
    static_ffmpeg.add_paths()
    ffmpeg_path = shutil.which("ffmpeg")
    return os.path.dirname(ffmpeg_path) if ffmpeg_path else None


yt_dlp = ensure_package("yt_dlp", "yt-dlp")
FFMPEG_DIR = setup_ffmpeg()


def inject_styles():
    st.html(
        """
        <style>
        /* Custom layout. Widget colors, type, and radii live in .streamlit/config.toml. */

        :root {
            --bg-base: #0c1220;
            --bg-card: #161e31;
            --bg-inset: #10182a;
            --border: #2c3854;
            --text: #e8eef9;
            --text-muted: #b7c3d9;
            --indigo: #5346d4;
            --cyan: #67e8f9;
            --radius: 16px;
            --radius-sm: 12px;
        }

        .stApp {
            background-color: var(--bg-base) !important;
            background-image:
                radial-gradient(880px 380px at 8% -12%, rgba(83, 70, 212, 0.2), transparent 58%),
                radial-gradient(640px 320px at 100% -8%, rgba(103, 232, 249, 0.07), transparent 46%) !important;
            color: var(--text);
            font-family: Manrope, "Segoe UI", sans-serif;
        }

        .block-container {
            max-width: 800px;
        }

        #MainMenu, footer { visibility: hidden; }
        header[data-testid="stHeader"] { background: transparent; }

        .stApp :focus-visible {
            outline: 2px solid var(--cyan);
            outline-offset: 2px;
        }

        .app-topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.85rem 1.25rem;
            margin: 0 0 1.35rem;
            flex-wrap: wrap;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 0.7rem;
            min-width: 0;
        }

        .brand-glyph {
            width: 2.15rem;
            height: 2.15rem;
            border-radius: 0.7rem;
            display: inline-flex;
            align-items: flex-end;
            justify-content: center;
            gap: 0.16rem;
            padding: 0.42rem 0.4rem;
            background: linear-gradient(160deg, #3a3278 0%, #161e31 70%);
            border: 1px solid #3d4c72;
            box-shadow: inset 0 0 0 1px rgba(103, 232, 249, 0.12);
            flex: none;
        }

        .brand-glyph span {
            display: block;
            width: 0.22rem;
            border-radius: 999px;
            background: #d9e2ff;
        }

        .brand-glyph span:nth-child(1) { height: 0.45rem; }
        .brand-glyph span:nth-child(2) { height: 0.85rem; background: var(--cyan); }
        .brand-glyph span:nth-child(3) { height: 0.62rem; }

        .brand-name {
            font-family: Fraunces, Georgia, serif;
            font-size: 1.35rem;
            font-weight: 560;
            letter-spacing: -0.03em;
            line-height: 1;
            color: #f4f7ff;
        }

        .brand-version {
            display: block;
            margin-top: 0.18rem;
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 0.04em;
            color: var(--text-muted);
        }

        .sys-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            font-size: 0.78rem;
            font-weight: 650;
            padding: 0.32rem 0.7rem 0.32rem 0.45rem;
            border-radius: 999px;
            border: 1px solid var(--border);
            background: var(--bg-card);
            color: var(--text);
            white-space: nowrap;
        }

        .sys-mark {
            width: 0.55rem;
            height: 0.55rem;
            flex: none;
        }

        .sys-pill.ok .sys-mark {
            border-radius: 999px;
            background: #3dbf86;
            box-shadow: 0 0 0 3px rgba(61, 191, 134, 0.18);
        }

        .sys-pill.bad .sys-mark {
            border-radius: 2px;
            background: transparent;
            border: 2px solid #ffb4b4;
        }

        .hero-card {
            position: relative;
            overflow: hidden;
            background:
                linear-gradient(180deg, rgba(83, 70, 212, 0.16), rgba(22, 30, 49, 0.2) 32%, var(--bg-card) 100%);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 1.35rem 1.3rem 1.15rem;
            box-shadow: 0 16px 40px rgba(3, 6, 16, 0.28);
            margin-bottom: 1.35rem;
        }

        .hero-card::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: linear-gradient(90deg, var(--cyan), var(--indigo) 46%, transparent 88%);
        }

        .hero-title {
            font-family: Fraunces, Georgia, serif;
            font-size: clamp(1.7rem, 4.6vw, 2.2rem);
            font-weight: 560;
            letter-spacing: -0.03em;
            line-height: 1.15;
            margin: 0 0 0.45rem;
            color: #f7f8ff;
        }

        .hero-lead {
            margin: 0;
            max-width: 40rem;
            color: var(--text-muted);
            line-height: 1.55;
            font-size: 1rem;
        }

        .flow {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 0.4rem;
            list-style: none;
            margin: 1rem 0 0;
            padding: 0;
        }

        .flow li {
            position: relative;
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            color: #d7def2;
            background: rgba(8, 12, 22, 0.28);
            border: 1px solid var(--border);
            border-radius: 999px;
            padding: 0.22rem 0.65rem 0.22rem 0.28rem;
            font-size: 0.78rem;
            font-weight: 650;
        }

        .flow li:not(:last-child)::after {
            content: "";
            position: absolute;
            left: calc(100% + 0.08rem);
            top: 50%;
            width: 0.45rem;
            height: 1px;
            background: var(--cyan);
        }

        .flow-index {
            width: 1.15rem;
            height: 1.15rem;
            border-radius: 999px;
            display: inline-grid;
            place-items: center;
            background: var(--indigo);
            color: #fff;
            font-size: 0.68rem;
            font-weight: 700;
        }

        .section-title {
            font-size: 1.02rem;
            font-weight: 700;
            letter-spacing: -0.015em;
            color: var(--text);
            margin: 0 0 0.55rem;
        }

        .section-count {
            display: inline-block;
            margin-left: 0.4rem;
            padding: 0.05rem 0.45rem;
            border-radius: 999px;
            border: 1px solid var(--border);
            color: var(--text-muted);
            font-size: 0.75rem;
            font-weight: 650;
            vertical-align: 0.1rem;
        }

        .helper-text {
            font-size: 0.92rem;
            color: var(--text-muted);
            margin: 0 0 0.85rem;
            line-height: 1.5;
        }

        .st-key-draft_url_input [data-testid="stWidgetLabel"],
        .st-key-output_format [data-testid="stWidgetLabel"] {
            color: var(--text);
            font-weight: 700;
        }

        .st-key-draft_url_input input {
            background: var(--bg-inset) !important;
            color: var(--text) !important;
            border: 1px solid #3d4d6e !important;
            border-radius: 0.8rem !important;
            min-height: 3.1rem;
            font-size: 1.02rem;
            padding: 0.75rem 0.9rem !important;
        }

        .st-key-draft_url_input input::placeholder {
            color: #aeb9cf;
            opacity: 1;
        }

        .st-key-draft_url_input input:focus-visible {
            border-color: #8b7cf6 !important;
            box-shadow: 0 0 0 4px rgba(103, 232, 249, 0.16) !important;
        }

        .st-key-output_format [data-testid="stRadio"] {
            width: 100%;
        }

        .st-key-output_format [data-testid="stRadioGroup"] {
            display: grid !important;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.75rem;
            width: 100% !important;
            align-items: stretch !important;
        }

        .st-key-output_format [data-testid="stRadioGroup"] > div {
            min-width: 0;
            margin: 0 !important;
            padding: 0.85rem 0.95rem 0.8rem;
            border: 1px solid var(--border);
            border-radius: 14px;
            background: var(--bg-inset);
        }

        .st-key-output_format [data-testid="stRadioGroup"] > div[data-selected="true"] {
            border-color: #8b7cf6;
            background: linear-gradient(180deg, rgba(83, 70, 212, 0.28), rgba(16, 24, 42, 0.94));
            box-shadow: inset 3px 0 0 var(--cyan);
        }

        .st-key-output_format [data-testid="stRadioOption"] {
            font-weight: 750;
            color: var(--text);
        }

        .st-key-output_format [data-testid="stRadioCaption"] {
            color: var(--text-muted);
            font-size: 0.84rem;
            line-height: 1.45;
        }

        .st-key-output_format [data-testid="stRadioGroup"] > div:has([data-focus-visible="true"]) {
            outline: 2px solid var(--cyan);
            outline-offset: 2px;
        }

        .st-key-add_to_queue button,
        .st-key-start_conversion button,
        .st-key-zip_download button,
        [class*="st-key-saved_dl_"] button,
        [class*="st-key-rm_"] button {
            min-height: 2.75rem;
            font-weight: 700;
            border-radius: 0.75rem !important;
        }

        .st-key-add_to_queue button,
        [class*="st-key-saved_dl_"] button,
        [class*="st-key-rm_"] button {
            background: #1c2640 !important;
            color: var(--text) !important;
            border: 1px solid #4a5a80 !important;
        }

        .st-key-add_to_queue button:hover,
        [class*="st-key-saved_dl_"] button:hover,
        [class*="st-key-rm_"] button:hover {
            border-color: var(--cyan) !important;
            background: #243050 !important;
        }

        .st-key-start_conversion button,
        .st-key-zip_download button {
            background: var(--indigo) !important;
            color: #fff !important;
            border: 1px solid #6d62e4 !important;
            box-shadow: 0 10px 24px rgba(83, 70, 212, 0.28);
        }

        .st-key-start_conversion button:hover:not(:disabled),
        .st-key-zip_download button:hover:not(:disabled) {
            border-color: var(--cyan) !important;
        }

        .st-key-start_conversion button:disabled {
            opacity: 1 !important;
            background: #232a3d !important;
            color: #9aa6bf !important;
            border: 1px dashed #4a5874 !important;
            box-shadow: none !important;
            cursor: not-allowed !important;
        }

        [class*="st-key-rm_"] button {
            min-height: 2.25rem;
        }

        .queue-card {
            border: 1px solid var(--border);
            border-left-width: 3px;
            border-radius: var(--radius-sm);
            padding: 0.85rem 0.95rem 0.75rem;
            margin-bottom: 0.35rem;
            background: var(--bg-inset);
        }

        .queue-card.is-pending { border-left-style: dashed; border-left-color: #8b97ad; }
        .queue-card.is-processing { border-left-color: #8b7cf6; }
        .queue-card.is-completed { border-left-color: #3dbf86; }
        .queue-card.is-error { border-left-color: #e06a6a; }

        .queue-head {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 0.75rem;
        }

        .queue-card-title {
            font-weight: 700;
            color: #f4f7ff;
            font-size: 1rem;
            line-height: 1.35;
            margin: 0;
            word-break: break-word;
        }

        .queue-meta {
            display: grid;
            gap: 0.45rem;
            margin: 0.7rem 0 0;
        }

        .queue-meta div {
            min-width: 0;
        }

        .queue-meta dt {
            margin: 0;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.01em;
            color: #aeb9cf;
        }

        .queue-meta dd {
            margin: 0.12rem 0 0;
            color: var(--text-muted);
            font-size: 0.86rem;
            line-height: 1.4;
            word-break: break-word;
        }

        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            flex: none;
            font-size: 0.72rem;
            font-weight: 700;
            padding: 0.22rem 0.5rem;
            border-radius: 999px;
            border: 1px solid transparent;
        }

        .status-badge::before {
            content: "";
            width: 0.42rem;
            height: 0.42rem;
            flex: none;
        }

        .status-badge.pending {
            color: #d7deee;
            background: #1c2438;
            border-color: #3a4660;
        }

        .status-badge.pending::before {
            border: 1.5px solid currentColor;
            border-radius: 999px;
        }

        .status-badge.processing {
            color: #d6e0ff;
            background: #1a2340;
            border-color: #44558a;
        }

        .status-badge.processing::before {
            background: currentColor;
            border-radius: 2px;
        }

        .status-badge.completed {
            color: #c9f6df;
            background: #13281f;
            border-color: #2f6b4e;
        }

        .status-badge.completed::before {
            background: currentColor;
            border-radius: 999px;
        }

        .status-badge.error {
            color: #ffd0d0;
            background: #2a161c;
            border-color: #7a3b3b;
        }

        .status-badge.error::before {
            background: currentColor;
            border-radius: 1px;
            transform: rotate(45deg);
        }

        .empty-queue {
            text-align: center;
            padding: 0.85rem 0.4rem 0.35rem;
        }

        .empty-mark {
            width: 2.3rem;
            height: 2.3rem;
            margin: 0 auto 0.75rem;
            border-radius: 999px;
            border: 1px dashed #4a5a80;
            background: radial-gradient(circle at 50% 50%, rgba(103, 232, 249, 0.18), transparent 62%);
        }

        .empty-title {
            margin: 0 0 0.35rem;
            color: var(--text);
            font-size: 1.02rem;
            font-weight: 700;
        }

        .empty-copy {
            margin: 0 auto;
            max-width: 34rem;
            color: var(--text-muted);
            font-size: 0.92rem;
            line-height: 1.5;
        }

        @media (max-width: 700px) {
            .app-topbar {
                flex-direction: column;
                align-items: flex-start;
            }

            .st-key-output_format [data-testid="stRadioGroup"] {
                grid-template-columns: 1fr !important;
            }

            .queue-head {
                flex-direction: column;
            }
        }

        @media (prefers-reduced-motion: reduce) {
            .stApp *,
            .stApp *::before,
            .stApp *::after {
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
                scroll-behavior: auto !important;
            }
        }
        </style>
        """
    )


def init_session_state():
    if "queue" not in st.session_state:
        st.session_state.queue = []
    if "item_state" not in st.session_state:
        st.session_state.item_state = {}
    if "results" not in st.session_state:
        st.session_state.results = []
    if "draft_url_input" not in st.session_state:
        st.session_state.draft_url_input = ""


def format_label(fmt: str) -> str:
    return "MP3" if "MP3" in fmt else "MP4"


def format_choice(fmt: str) -> str:
    if fmt == FORMAT_MP3:
        return ":material/audio_file: MP3"
    return ":material/movie: MP4"


def add_to_queue():
    url = (st.session_state.draft_url_input or "").strip()
    if not url:
        return
    if url not in st.session_state.queue:
        st.session_state.queue.append(url)
        st.session_state.item_state[url] = {
            "status": STATUS_PENDING,
            "title": "",
            "error": "",
        }
    st.session_state.draft_url_input = ""


def remove_from_queue(index: int):
    if 0 <= index < len(st.session_state.queue):
        url = st.session_state.queue.pop(index)
        st.session_state.item_state.pop(url, None)
        st.session_state.results = [r for r in st.session_state.results if r.get("url") != url]


def render_status_badge(status: str) -> str:
    labels = {
        STATUS_PENDING: ("Waiting", "pending"),
        STATUS_PROCESSING: ("Processing", "processing"),
        STATUS_COMPLETED: ("Completed", "completed"),
        STATUS_ERROR: ("Error", "error"),
    }
    text, css = labels.get(status, ("Unknown", "pending"))
    return f'<span class="status-badge {css}" aria-label="Status: {text}">{text}</span>'


def safe_name(title, fallback):
    cleaned = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).strip()
    return cleaned or fallback


def cookies_path():
    path = PROJECT_ROOT / "cookies.txt"
    return str(path) if path.is_file() else None


def download_one(url, index, fmt, status_cb, progress_cb):
    def hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                pct = min(max(downloaded / total, 0.0), 1.0)
                progress_cb(pct)
                status_cb(f"Downloading… {int(pct * 100)}%")
        elif d["status"] == "finished":
            status_cb("Processing file…")

    with tempfile.TemporaryDirectory() as tmpdir:
        outtmpl = str(Path(tmpdir) / f"item_{index}_%(id)s.%(ext)s")

        ydl_opts = {
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "progress_hooks": [hook],
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
        }
        if FFMPEG_DIR:
            ydl_opts["ffmpeg_location"] = FFMPEG_DIR
        cookiefile = cookies_path()
        if cookiefile:
            ydl_opts["cookiefile"] = cookiefile

        if "MP3" in fmt:
            ydl_opts.update({
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            })
            final_ext = "mp3"
            mime = "audio/mpeg"
        else:
            ydl_opts.update({
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "merge_output_format": "mp4",
            })
            final_ext = "mp4"
            mime = "video/mp4"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", f"video_{index}")

        candidates = list(Path(tmpdir).glob(f"item_{index}_*.{final_ext}"))
        if not candidates:
            candidates = list(Path(tmpdir).glob(f"item_{index}_*.*"))
        if not candidates:
            raise FileNotFoundError("No output file was produced by yt-dlp.")

        output_file = max(candidates, key=lambda p: p.stat().st_mtime)
        file_bytes = output_file.read_bytes()

    filename = f"{safe_name(title, f'download_{index}')}.{final_ext}"
    return title, filename, file_bytes, mime


def build_zip(results):
    buffer = io.BytesIO()
    used = {}
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in results:
            name = r["filename"]
            if name in used:
                used[name] += 1
                stem, ext = os.path.splitext(name)
                name = f"{stem}_{used[name]}{ext}"
            else:
                used[name] = 0
            zf.writestr(name, r["bytes"])
    buffer.seek(0)
    return buffer.getvalue()


def render_queue_cards(queue, fmt: str):
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

    for i, url in enumerate(queue):
        state = st.session_state.item_state.get(url, {})
        status = state.get("status", STATUS_PENDING)
        title = html.escape(state.get("title") or f"Item {i + 1}")
        safe_url = html.escape(url)
        err = state.get("error", "")
        badge = render_status_badge(status)
        st.markdown(
            f"""
            <article class="queue-card is-{status}">
                <div class="queue-head">
                    <h3 class="queue-card-title">{title}</h3>
                    {badge}
                </div>
                <dl class="queue-meta">
                    <div>
                        <dt>Source</dt>
                        <dd>{safe_url}</dd>
                    </div>
                    <div>
                        <dt>Format</dt>
                        <dd>{format_label(fmt)}</dd>
                    </div>
                </dl>
            </article>
            """,
            unsafe_allow_html=True,
        )
        if status == STATUS_ERROR and err:
            st.caption(f"Error detail: {err}")
        with st.container(horizontal=True, horizontal_alignment="right"):
            st.button(
                "Remove",
                key=f"rm_{i}_{hash(url) % 10_000}",
                on_click=remove_from_queue,
                args=(i,),
                icon=":material/delete:",
                help="Remove this item from the queue",
            )


# ----------------------------------------------------------------------
# App
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="StreamTune",
    page_icon=":material/graphic_eq:",
    layout="centered",
    initial_sidebar_state="collapsed",
)

inject_styles()
init_session_state()

ffmpeg_ok = bool(FFMPEG_DIR)
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
    st.caption("One authorized URL per queue item.")
    st.button(
        "Add to queue",
        type="secondary",
        width="stretch",
        on_click=add_to_queue,
        icon=":material/playlist_add:",
        key="add_to_queue",
        help="Adds the URL above to the conversion queue",
    )

st.space("small")
with st.container(border=True, key="format_card"):
    format_type = st.radio(
        "Output format",
        [FORMAT_MP3, FORMAT_MP4],
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

st.space("small")
queue_count = f'<span class="section-count">{queue_len}</span>' if queue_len else ""
st.markdown(
    f'<h2 class="section-title">Queue{queue_count}</h2>',
    unsafe_allow_html=True,
)
with st.container(border=True, key="queue_panel"):
    render_queue_cards(st.session_state.queue, format_type)

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
    help="Convert all queued items to the selected MP3 or MP4 format",
):
    st.session_state.results = []
    urls = list(st.session_state.queue)
    total = len(urls)

    for index, url in enumerate(urls):
        st.session_state.item_state[url] = {
            "status": STATUS_PROCESSING,
            "title": st.session_state.item_state.get(url, {}).get("title", f"Item {index + 1}"),
            "error": "",
        }
        st.markdown(f"**Converting item {index + 1} of {total}**")
        status = st.empty()
        bar = st.progress(0)
        status.caption("Starting…")

        try:
            title, filename, file_bytes, mime = download_one(
                url,
                index,
                format_type,
                status_cb=lambda m: status.caption(m),
                progress_cb=lambda p: bar.progress(p),
            )
            bar.progress(1.0)
            status.success(f"Completed: {title}", icon=":material/check_circle:")
            st.session_state.item_state[url] = {
                "status": STATUS_COMPLETED,
                "title": title,
                "error": "",
            }
            st.session_state.results.append({
                "url": url,
                "title": title,
                "filename": filename,
                "bytes": file_bytes,
                "mime": mime,
            })
        except Exception as exc:
            status.empty()
            st.error(
                f"Conversion failed for item {index + 1}.",
                icon=":material/error:",
            )
            st.session_state.item_state[url] = {
                "status": STATUS_ERROR,
                "title": st.session_state.item_state.get(url, {}).get("title", f"Item {index + 1}"),
                "error": str(exc),
            }

    if st.session_state.results:
        st.balloons()

if st.session_state.results:
    st.markdown('<h2 class="section-title">Downloads</h2>', unsafe_allow_html=True)
    for i, item in enumerate(st.session_state.results):
        st.download_button(
            label=f"Download {item['filename']}",
            data=item["bytes"],
            file_name=item["filename"],
            mime=item["mime"],
            key=f"saved_dl_{i}_{hash(item['url']) % 10_000}",
            icon=":material/download:",
            type="secondary",
            width="stretch",
        )

if len(st.session_state.results) > 1:
    st.space("small")
    zip_bytes = build_zip(st.session_state.results)
    st.download_button(
        label=f"Download all as ZIP ({len(st.session_state.results)} files)",
        data=zip_bytes,
        file_name="streamtune_downloads.zip",
        mime="application/zip",
        icon=":material/folder_zip:",
        type="primary",
        width="stretch",
        key="zip_download",
    )
