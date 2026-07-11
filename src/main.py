import streamlit as st
import yt_dlp
import os
import streamlit.components.v1 as components

# Set up page configuration
st.set_page_config(page_title="YouTube Multi-Downloader", page_icon="🎬", layout="centered")

st.title("🎬 YouTube Media Downloader")
st.write("Files will download automatically to your browser's default Downloads folder when finished.")

# Text area to support multiple links (one per line)
urls_input = st.text_area("Enter YouTube Video URL(s):", placeholder="https://www.youtube.com/watch?v=...\nhttps://www.youtube.com/watch?v=...", height=120)

# Format selection dropdown
format_type = st.selectbox("Select Download Format:", ["MP3 (Audio Only)", "MP4 (Full Video)"])

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

if urls_input:
    url_list = [url.strip() for url in urls_input.split('\n') if url.strip()]
    
    if st.button("Start Batch Download", type="primary"):
        total_videos = len(url_list)
        st.info(f"Found {total_videos} link(s) to process.")
        
        for index, url in enumerate(url_list):
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

            # Use unique temp template to avoid collision
            temp_template = f"media_dl_{index}_%(id)s.%(ext)s"
            
            ydl_opts = {
                'outtmpl': temp_template,
                'quiet': False,  # Turned OFF quiet mode to let metadata stream correctly
                'progress_hooks': [ytdl_hook],
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
                    # Extract info first
                    info = ydl.extract_info(url, download=True)
                    video_id = info.get('id', '')
                    video_title = info.get('title', f'video_{index}')
                    
                    # Target filename after formatting
                    actual_filename = f"media_dl_{index}_{video_id}.{final_ext}"
                    
                    # Clean title for legal filename usage
                    safe_title = "".join([c for c in video_title if c.isalpha() or c.isdigit() or c in ' _-']).rstrip()
                    if not safe_title:
                        safe_title = "downloaded_file"

                if os.path.exists(actual_filename):
                    status_placeholder.text("Preparing file transmission...")
                    with open(actual_filename, "rb") as file:
                        file_bytes = file.read()
                    
                    os.remove(actual_filename)
                    progress_bar.progress(1.0)
                    status_placeholder.text(f"🎉 Successfully downloaded: {video_title}")
                    
                    trigger_auto_download(file_bytes, f"{safe_title}.{final_ext}", mime_type)
                    st.success(f"Sent to your browser downloads folder: {safe_title}.{final_ext}")
                else:
                    st.error(f"Error: Post-processed file '{actual_filename}' not found on server.")
            except Exception as e:
                status_placeholder.text("Execution halted.")
                st.error(f"An error occurred while processing link {index + 1}: {str(e)}")
        
        st.markdown("---")
        st.balloons()
        st.success("All tasks completed!")