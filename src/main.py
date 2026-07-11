import streamlit as st
import yt_dlp
import os
import streamlit.components.v1 as components

# Set up page configuration
st.set_page_config(page_title="YouTube Multi-Downloader", page_icon="🎬", layout="centered")

st.title("🎬 YouTube Media Downloader")
st.write("Add your YouTube links, customize preferences, and download all media at once.")

# Initialize the list of URLs in session state if it doesn't exist
if 'url_inputs' not in st.session_state:
    st.session_state.url_inputs = [""]

# --- Global Settings Section ---
st.markdown("### ⚙️ Global Settings")
# Using columns to place format selection neatly
col_format, col_spacer = st.columns([2, 2])
with col_format:
    format_type = st.selectbox("Select Download Format:", ["MP3 (Audio Only)", "MP4 (Full Video)"])

st.markdown("---")

# --- Video Links Section ---
st.markdown("### 🔗 Video Links")

# Callback functions for dynamic UI adjustment to prevent state loss
def add_input_field():
    st.session_state.url_inputs.append("")

def remove_input_field(index_to_remove):
    # Ensure at least one input field remains visible
    if len(st.session_state.url_inputs) > 1:
        st.session_state.url_inputs.pop(index_to_remove)
    else:
        st.session_state.url_inputs[0] = ""

# Wrap the links inside a clean bordered container
with st.container(border=True):
    for i in range(len(st.session_state.url_inputs)):
        # Create a split row: 85% for the text input, 15% for the delete button
        col_input, col_delete = st.columns([6, 1])
        
        with col_input:
            st.session_state.url_inputs[i] = st.text_input(
                f"YouTube URL #{i + 1}",
                value=st.session_state.url_inputs[i],
                key=f"url_field_{i}",
                placeholder="https://www.youtube.com/watch?v=...",
                label_visibility="collapsed" if i > 0 else "visible" # Hide label for subsequent fields to look cleaner
            )
            
        with col_delete:
            # Adjust padding alignment for the trash button depending on whether it has a label above it
            st.markdown("<div style='padding-top: 28px;'></div>" if i == 0 else "<div style='padding-top: 4px;'></div>", unsafe_allow_html=True)
            st.button("🗑️", key=f"del_btn_{i}", on_click=remove_input_field, args=(i,))

    st.markdown(" ")
    # Action button centered/aligned inside the container to add new fields
    st.button("➕ Add Another Video", on_click=add_input_field)

# Filter out empty or whitespace-only strings from the input list
valid_urls = [url.strip() for url in st.session_state.url_inputs if url.strip()]

st.markdown("---")

# JavaScript helper for triggering automatic browser downloads
def trigger_auto_download(file_bytes, filename, mime_type):
    import base64
    b64 = base64.b64encode(file_bytes).decode()
    dl_script = f"""
    <script>
    var a = document.createElement('a');
    a.href = 'data:{mime_type};base64,{b64}';
    a.download = '{filename}';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    </script>
    """
    components.html(dl_script, height=0, width=0)

# --- Main Download Execution Block ---
if st.button("🚀 Start Batch Download", type="primary", disabled=len(valid_urls) == 0, use_container_width=True):
    total_videos = len(valid_urls)
    st.info(f"Processing {total_videos} valid link(s)...")
    
    for index, url in enumerate(valid_urls):
        st.markdown("---")
        st.subheader(f"Processing ({index + 1}/{total_videos}):")
        
        status_placeholder = st.empty()
        progress_bar = st.progress(0)
        
        status_placeholder.text("Connecting to YouTube and analyzing metadata...")
        
        def ytdl_hook(d):
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                if total > 0:
                    percent = downloaded / total
                    percent = min(max(percent, 0.0), 1.0)
                    progress_bar.progress(percent)
                    status_placeholder.text(f"Downloading: {int(percent * 100)}% completed")
            elif d['status'] == 'finished':
                status_placeholder.text("Download complete! Converting media format...")

        temp_template = f"media_dl_{index}_%(id)s.%(ext)s"
        
        ydl_opts = {
            'outtmpl': temp_template,
            'quiet': False,
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
                status_placeholder.text("File processed successfully!")
                with open(actual_filename, "rb") as file:
                    file_bytes = file.read()
                
                os.remove(actual_filename)
                progress_bar.progress(1.0)
                status_placeholder.text(f"🎉 Ready: {video_title}")
                
                # Manual download button backup styled nicely
                st.download_button(
                    label=f"💾 Save {safe_title}.{final_ext}",
                    data=file_bytes,
                    file_name=f"{safe_title}.{final_ext}",
                    mime=mime_type,
                    key=f"dl_btn_{index}",
                    use_container_width=True
                )
                
                # Automated browser download call
                trigger_auto_download(file_bytes, f"{safe_title}.{final_ext}", mime_type)
            else:
                st.error(f"Error: Post-processed file '{actual_filename}' not found.")
        except Exception as e:
            status_placeholder.text("Execution halted.")
            st.error(f"An error occurred while processing link {index + 1}: {str(e)}")
    
    st.markdown("---")
    st.balloons()
    st.success("All tasks completed!")