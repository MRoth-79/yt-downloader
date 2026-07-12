import os
import io
import sys
import shutil
import zipfile
import tempfile
import subprocess
import importlib
from pathlib import Path

import streamlit as st

# ----------------------------------------------------------------------
# Bootstrap: ensure yt-dlp + FFmpeg are available
# ----------------------------------------------------------------------
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

# ----------------------------------------------------------------------
# Page config + styling
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="StreamTune - Premium Downloader",
    page_icon="🎵",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
    <style>
    .main-title {
        font-size: 3rem !important;
        font-weight: 800 !important;
        background: linear-gradient(45deg, #FF4B4B, #FF8585);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .subtitle { color: #808495; font-size: 1.1rem; margin-bottom: 2rem; }
    div.stButton > button:first-child { transition: all 0.3s ease; border-radius: 8px; }
    div[data-testid="stActionButton"] button {
        border-color: transparent !important;
        background-color: transparent !important;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-title">StreamTune</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">The ultimate minimalist, high-speed YouTube media converter.</p>', unsafe_allow_html=True)

if FFMPEG_DIR:
    st.caption(f"✅ FFmpeg ready ({FFMPEG_DIR})")
else:
    st.error("❌ FFmpeg could not be set up automatically. MP3/MP4 conversion may fail.")

# ----------------------------------------------------------------------
# Session state
# ----------------------------------------------------------------------
if "url_inputs" not in st.session_state:
    st.session_state.url_inputs = [""]
if "results" not in st.session_state:
    st.session_state.results = []

valid_urls = [u.strip() for u in st.session_state.url_inputs if u.strip()]

col_stat1, col_stat2 = st.columns(2)
with col_stat1:
    st.metric(label="Queue Size", value=f"{len(valid_urls)} Video(s)")
with col_stat2:
    st.metric(label="Status", value="Ready" if len(valid_urls) > 0 else "Idle")

st.markdown(" ")
st.markdown("#### ⚙️ Choose Output Preferences")
format_type = st.radio(
    "Select Download Format:",
    ["MP3 (Audio Only)", "MP4 (Full Video)"],
    index=0,
    horizontal=True,
    label_visibility="collapsed",
)

st.markdown(" ")
st.markdown("#### 🔗 Your Download Queue")

def add_input_field():
    st.session_state.url_inputs.append("")

def remove_input_field(index_to_remove):
    if len(st.session_state.url_inputs) > 1:
        st.session_state.url_inputs.pop(index_to_remove)
    else:
        st.session_state.url_inputs[0] = ""

with st.container(border=True):
    for i in range(len(st.session_state.url_inputs)):
        col_input, col_delete = st.columns([12, 1])
        with col_input:
            st.session_state.url_inputs[i] = st.text_input(
                f"URL #{i + 1}",
                value=st.session_state.url_inputs[i],
                key=f"url_field_{i}",
                placeholder="Paste YouTube link here...",
                label_visibility="collapsed",
            )
        with col_delete:
            st.button("🗑️", key=f"del_btn_{i}", on_click=remove_input_field, args=(i,), help="Remove link")

    st.markdown(" ")
    st.button("✨ Add Next Track", on_click=add_input_field, type="secondary")

# De-duplicate
seen = set()
valid_urls = []
for u in st.session_state.url_inputs:
    u = u.strip()
    if u and u not in seen:
        seen.add(u)
        valid_urls.append(u)

st.markdown(" ")

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def safe_name(title, fallback):
    cleaned = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).strip()
    return cleaned or fallback

def download_one(url, index, fmt, status_cb, progress_cb):
    def hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                pct = min(max(downloaded / total, 0.0), 1.0)
                progress_cb(pct)
                status_cb(f"Streaming: {int(pct * 100)}%")
        elif d["status"] == "finished":
            status_cb("Compiling media file...")

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
        # Use cookies.txt if present (helps bypass bot checks on cloud)
        if os.path.exists("cookies.txt"):
            ydl_opts["cookiefile"] = "cookies.txt"

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

# ----------------------------------------------------------------------
# Main execution
# ----------------------------------------------------------------------
if st.button("🚀 Process Batch & Download", type="primary",
             disabled=len(valid_urls) == 0, use_container_width=True):
    st.session_state.results = []
    total = len(valid_urls)

    for index, url in enumerate(valid_urls):
        st.markdown(f"##### 📦 Extracting Media ({index + 1}/{total})")
        status = st.empty()
        bar = st.progress(0)
        status.caption("Processing...")

        try:
            title, filename, file_bytes, mime = download_one(
                url, index, format_type,
                status_cb=lambda m: status.caption(m),
                progress_cb=lambda p: bar.progress(p),
            )
            bar.progress(1.0)
            status.success(f"🎉 Ready: {title}")

            st.session_state.results.append(
                {"title": title, "filename": filename, "bytes": file_bytes, "mime": mime}
            )

            st.download_button(
                label=f"💾 Save {filename}",
                data=file_bytes,
                file_name=filename,
                mime=mime,
                key=f"dl_btn_{index}",
                use_container_width=True,
            )
        except Exception as e:
            status.empty()
            st.error(f"Extraction failed for link {index + 1}: {e}")

    if st.session_state.results:
        st.balloons()

# Bundled ZIP
if len(st.session_state.results) > 1:
    st.markdown("#### 📦 Download Everything")
    zip_bytes = build_zip(st.session_state.results)
    st.download_button(
        label=f"⬇️ Download all {len(st.session_state.results)} files as ZIP",
        data=zip_bytes,
        file_name="streamtune_downloads.zip",
        mime="application/zip",
        use_container_width=True,
    )
