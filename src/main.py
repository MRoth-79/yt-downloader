import streamlit as st
import yt_dlp
import os
import io

# Set up page configuration
st.set_page_config(page_title="YouTube Downloader", page_icon="🎬", layout="centered")

# App header and description
st.title("🎬 YouTube Media Downloader")
st.write("Paste a YouTube link, select your preferred format, and download directly to your device.")

# Input field for the YouTube URL
url = st.text_input("Enter YouTube Video URL:", placeholder="https://www.youtube.com/watch?v=...")

# Format selection dropdown
format_type = st.selectbox("Select Download Format:", ["MP3 (Audio Only)", "MP4 (Full Video)"])

if url:
    # Trigger processing when the button is clicked
    if st.button("Process Video for Download", type="primary"):
        with st.spinner("Processing and downloading in the cloud, please wait..."):
            
            # Temporary base filename on the server
            temp_filename = "downloaded_media"
            
            # Base configuration for yt-dlp
            ydl_opts = {
                'outtmpl': f"{temp_filename}.%(ext)s",
                'quiet': True,
            }

            # Adjust settings based on the selected format
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
            else:
                ydl_opts.update({
                    'format': 'best[ext=mp4]/best',
                })
                final_ext = "mp4"

            try:
                # Execute the download process on the server backend
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    actual_filename = f"{temp_filename}.{final_ext}"
                    video_title = info.get('title', 'youtube_media')

                # Verify file creation and prepare it for browser download
                if os.path.exists(actual_filename):
                    with open(actual_filename, "rb") as file:
                        file_bytes = file.read()
                    
                    # Remove the physical file from the server to keep storage clean
                    os.remove(actual_filename)
                    
                    st.success(f"🎉 Successfully processed: '{video_title}'")
                    
                    # Download button to deliver the file to the client's browser
                    st.download_button(
                        label=f"⬇️ Click Here to Download {final_ext.upper()}",
                        data=file_bytes,
                        file_name=f"{video_title}.{final_ext}",
                        mime=f"audio/{final_ext}" if final_ext == "mp3" else f"video/{final_ext}"
                    )
                else:
                    st.error("Error: The file could not be generated on the server.")
            except Exception as e:
                st.error(f"An error occurred during processing: {str(e)}")