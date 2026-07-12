import streamlit as st
import yt_dlp
import os

# Try to automatically inject static-ffmpeg into system PATH if available (for local runs)
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    pass

# --- Page Configuration ---
st.set_page_config(
    page_title="StreamTune - Premium Downloader", 
    page_icon="🎵", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- Custom CSS for Modern Tech Look ---
st.markdown("""
    <style>
    /* Gradient Title Effect */
    .main-title {
        font-size: 3rem !important;
        font-weight: 800 !important;
        background: linear-gradient(45deg, #FF4B4B, #FF8585);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .subtitle {
        color: #808495;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    /* Smooth transition for hover elements */
    div.stButton > button:first-child {
        transition: all 0.3s ease;
        border-radius: 8px;
    }
    /* Trash button customization */
    div[data-testid="stActionButton"] button {
        border-color: transparent !important;
        background-color: transparent !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- Header Section ---
st.markdown('<h1 class="main-title">StreamTune</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">The ultimate minimalist, high-speed YouTube media converter.</p>', unsafe_allow_html=True)

# Initialize the list of URLs in session state if it doesn't exist
if 'url_inputs' not in st.session_state:
    st.session_state.url_inputs = [""]

# --- Quick Stats / Dashboard Feel ---
valid_urls = [url.strip() for url in st.session_state.url_inputs if url.strip()]
col_stat1, col_stat2 = st.columns(2)
with col_stat1:
    st.metric(label="Queue Size", value=f"{len(valid_urls)} Video(s)")
with col_stat2:
    st.metric(label="Status", value="Ready" if len(valid_urls) > 0 else "Idle")

st.markdown(" ")

# --- Global Settings Section (Modern Toggle) ---
st.markdown("#### ⚙️ Choose Output Preferences")
format_type = st.radio(
    "Select Download Format:",
    ["MP3 (Audio Only)", "MP4 (Full Video)"],
    index=0,
    horizontal=True,
    label_visibility="collapsed"
)

st.markdown(" ")

# --- Video Links Section ---
st.markdown("#### 🔗 Your Download Queue")

def add_input_field():
    st.session_state.url_inputs.append("")

def remove_input_field(index_to_remove):
    if len(st.session_state.url_inputs) > 1:
        st.session_state.url_inputs.pop(index_to_remove)
    else:
        st.session_state.url_inputs[0] = ""

# Clean, modern container with subtle border
with st.container(border=True):
    for i in range(len(st.session_state.url_inputs)):
        col_input, col_delete = st.columns([12, 1])
        
        with col_input:
            st.session_state.url_inputs[i] = st.text_input(
                f"URL #{i + 1}",
                value=st.session_state.url_inputs[i],
                key=f"url_field_{i}",
                placeholder="Paste YouTube link here...",
                label_visibility="collapsed"
            )
            
        with col_delete:
            st.button("🗑️", key=f"del_btn_{i}", on_click=remove_input_field, args=(i,), help="Remove link")

    st.markdown(" ")
    st.button("✨ Add Next Track", on_click=add_input_field, type="secondary")

st.markdown(" ")

# --- Main Download Execution Block ---
if st.button("🚀 Process Batch & Download", type="primary", disabled=len(valid_urls) == 0, use_container_width=True):
    total_videos = len(valid_urls)
    
    for index, url in enumerate(valid_urls):
        st.markdown(f"##### 📦 Extracting Media ({index + 1}/{total_videos})")
        
        status_placeholder = st.empty()
        progress_bar = st.progress(0)
        
        status_placeholder.caption("Analyzing link data...")
        
        def ytdl_hook(d):
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                if total > 0:
                    percent = downloaded / total
                    percent = min(max(percent, 0.0), 1.0)
                    progress_bar.progress(percent)
                    status_placeholder.caption(f"Downloading: {int(percent * 100)}%")
            elif d['status'] == 'finished':
                status_placeholder.caption("Converting format... Please hold on.")

        temp_template = f"media_dl_{index}_%(id)s.%(ext)s"
        
        ydl_opts = {
            'outtmpl': temp_template,
            'quiet': True,
            'progress_hooks': [ytdl_hook],
            'noplaylist': True,
        }

        if "MP3" in format_type:
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
            final_ext = "mp3"
            mime_type = "audio/mp3"
        else:
            ydl_opts.update({
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            })
            final_ext = "mp4"
            mime_type = "video/mp4"

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                video_id = info.get('id', '')
                video_title = info.get('title', f'video_{index}')
                
                actual_filename = f"media_dl_{index}_{video_id}.{final_ext}"
                safe_title = "".join([c for c in video_title if c.isalpha() or c.isdigit() or c in ' _-']).rstrip()
                if not safe_title:
                    safe_title = "downloaded_file"

            if os.path.exists(actual_filename):
                with open(actual_filename, "rb") as file:
                    file_bytes = file.read()
                
                os.remove(actual_filename)
                progress_bar.progress(1.0)
                status_placeholder.success(f"🎉 Success: {video_title}")
                
                st.download_button(
                    label=f"💾 Save {safe_title}.{final_ext}",
                    data=file_bytes,
                    file_name=f"{safe_title}.{final_ext}",
                    mime=mime_type,
                    key=f"dl_btn_{index}",
                    use_container_width=True
                )
            else:
                st.error("Error generating post-processed file.")
        except Exception as e:
            status_placeholder.empty()
            st.error(f"Failed to process link #{index + 1}: {str(e)}")
    
    st.balloons()