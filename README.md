# StreamTune

This repository is named `yt-downloader`, but the app it contains is called StreamTune.

[![CI](https://github.com/MRoth-79/yt-downloader/actions/workflows/ci.yml/badge.svg)](https://github.com/MRoth-79/yt-downloader/actions/workflows/ci.yml)

Local Streamlit app to convert authorized media sources to MP3 or MP4.

## Features

- Queue several URLs. The title, duration, and thumbnail are read when you add a link, so bad links are rejected early.
- Choose MP3 (128, 192, or 320 kbps) or MP4 (up to 4K, or best available).
- Items convert two at a time. Each item shows its own progress bar and final status.
- Failed items can be retried. Completed items are not converted again unless you change the format or quality.
- Download each file, or all files as one ZIP.
- Save all finished files into a folder you name. Folders are created in `Downloads\StreamTune` (existing files are never overwritten).
- Update yt-dlp from the Maintenance panel when sites change and downloads start failing. The update runs in the background and shows its result when it finishes.
- The queue and finished downloads are kept after a page refresh or an app restart. Leftover download folders older than 24 hours are deleted automatically.
- Playlist links are not supported yet. A video link that also points into a playlist downloads only that video.

## Requirements

- Windows, macOS, or Linux
- Python 3.10 or newer
- Internet access on first run (FFmpeg is downloaded automatically when it is not installed)

## Run

Windows: double-click `StreamTune.bat`. On first run it creates a `.venv` folder in the project and installs the dependencies there.

Or from a terminal:

```powershell
cd yt-downloader
python run.py
```

`run.py` installs or updates everything in `requirements.txt` and then starts the app.

After code updates: hard refresh the browser (`Ctrl+F5`) or restart the app.

## Optional: sign-in cookies

Place `cookies.txt` (exported from your browser in Netscape format) in the project root for videos that require sign-in. The file is ignored by Git. Never commit it.

## Development

```powershell
pip install -r requirements-dev.txt
ruff check .
ruff format --check .
python -m pytest
```

## Project layout

| Path | Purpose |
| --- | --- |
| `run.py` | Installs dependencies and launches the app |
| `src/main.py` | Streamlit UI (queue, conversion, downloads) |
| `src/downloader.py` | Download, conversion, file, and error helpers (no Streamlit dependency) |
| `src/styles.css` | Layout styles injected into the app |
| `.streamlit/config.toml` | Theme (colors, fonts, radii) |
| `tests/` | Unit tests for the helpers |

## License

StreamTune is released under the MIT License. See [LICENSE](LICENSE).
