# PanelForge — Local Manga CBZ Converter

A private, browser-based manga converter that runs entirely on your computer. Combine images, PDFs, ZIPs, and CBZ archives into a reader-ready CBZ file. No files are uploaded to the internet.

## Quick start

### Windows

1. Install [Python 3.10+](https://www.python.org/downloads/) and enable **Add Python to PATH**.
2. Double-click **`run_windows.bat`**.
3. The first run installs the required Python packages; later runs start immediately.

### Linux

```bash
chmod +x run_linux.sh
./run_linux.sh
```

The app opens at <http://127.0.0.1:5000>. Keep the terminal window open while using it; press Ctrl+C to stop.

> The app does not need internet to convert files. The first run may need internet once to install Flask, Pillow, and PyMuPDF. You can also pre-install `requirements.txt` from an offline Python package cache.

## Features

- Images: JPEG, PNG, WebP, BMP, GIF, and TIFF
- Documents/archives: PDF, ZIP, and CBZ
- Natural page ordering (`2` before `10`)
- JPEG, WebP, or lossless PNG output
- Adjustable quality and maximum dimensions
- Optional automatic double-page spread splitting
- Right-to-left manga and left-to-right comic ordering
- Embedded `ComicInfo.xml` metadata
- 2 GB combined upload limit
- ZIP path traversal protection

## Manual start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

On Windows, use `.venv\Scripts\python.exe` instead.

## Privacy

Processing occurs on localhost. Temporary files are deleted after each download, and the server listens only on `127.0.0.1` by default so other devices cannot access it.
