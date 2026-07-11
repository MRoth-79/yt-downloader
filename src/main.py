import streamlit as st
import yt_dlp
import os
import streamlit.components.v1 as components

# Set up page configuration
st.set_page_config(page_title="YouTube Multi-Downloader", page_icon="🎬", layout="centered")

st.title("🎬 YouTube Media Downloader")
st.write("Enter one or more YouTube links (one per line), select your format, and they will download automatically when ready.")

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
    # Split input by lines and remove empty lines or whitespace
    url_list = [url.strip() for url in urls_input.split('\n') if url.strip()]
    
    if st.button("Start Batch Download", type="primary"):
        total_videos = len(url_list)
        st.info(f"Found {total_videos} link(s) to process.")
        
        # Process each URL in the list one by one
        for index, url in enumerate(url_list):
            st.markdown("---")
            st.subheader(f"Processing ({index + 1}/{total_videos}):")
            
            # Create placeholders for dynamic status and progress bar updates
            status_placeholder = st.empty()
            progress_bar = st.progress(0)
            
            status_placeholder.text("Analyzing video metadata...")
            
            # yt-dlp hook to capture real-time download progress percentages
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

            temp_filename = f"media_stream_{index}"
            ydl_opts = {
                'outtmpl': f"{temp_filename}.%(ext)s",
                'quiet': True,
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
                    'format': 'best[ext=mp4]/best',
                })
                final_ext = "mp4"
                mime_type = "video/mp4"

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    actual_filename = f"{temp_filename}.{final_ext}"
                    video_title = info.get('title', f'video_{index}')
                    safe_title = "".join([c for c in video_title if c.isalpha() or c.isdigit() or c in ' _-']).rstrip()
                    if not safe_title:
                        safe_title = "downloaded_file"

                if os.path.exists(actual_filename):
                    status_placeholder.text("Sending file to browser...")
                    with open(actual_filename, "rb") as file:
                        file_bytes = file.read()
                    
                    os.remove(actual_filename)
                    progress_bar.progress(1.0)
                    status_placeholder.text(f"🎉 Successfully downloaded: {video_title}")
                    
                    # Inject JS to force the browser to save the file immediately
                    trigger_auto_download(file_bytes, f"{safe_title}.{final_ext}", mime_type)
                    st.success(f"Saved to your browser downloads folder: {safe_title}.{final_ext}")
                else:
                    st.error(f"Error: Could not locate processed file for link {index + 1}.")
            except Exception as e:
                st.error(f"Failed to process link {index + 1}: {str(e)}")
        
        st.markdown("---")
        st.balloons()
        st.success("All tasks completed!")