from __future__ import annotations

import io
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import fitz
from flask import Flask, after_this_request, jsonify, render_template, request, send_file
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config.update(MAX_CONTENT_LENGTH=2 * 1024 * 1024 * 1024)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
ARCHIVE_EXTENSIONS = {".zip", ".cbz"}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | ARCHIVE_EXTENSIONS | {".pdf"}


def natural_key(value: str):
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", value)]


def safe_archive_name(name: str) -> bool:
    path = Path(name)
    return not path.is_absolute() and ".." not in path.parts


def collect_images(input_dir: Path, work_dir: Path) -> list[Path]:
    images: list[Path] = []
    expanded = work_dir / "expanded"
    expanded.mkdir()
    pdf_index = 0

    for source in sorted(input_dir.iterdir(), key=lambda p: natural_key(p.name)):
        ext = source.suffix.lower()
        if ext in IMAGE_EXTENSIONS:
            images.append(source)
        elif ext in ARCHIVE_EXTENSIONS:
            target = expanded / f"archive_{len(images)}_{source.stem}"
            target.mkdir()
            with zipfile.ZipFile(source) as archive:
                for member in archive.infolist():
                    if member.is_dir() or not safe_archive_name(member.filename):
                        continue
                    if Path(member.filename).suffix.lower() not in IMAGE_EXTENSIONS:
                        continue
                    destination = target / member.filename
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as src, destination.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
            images.extend(sorted((p for p in target.rglob("*") if p.suffix.lower() in IMAGE_EXTENSIONS), key=lambda p: natural_key(str(p.relative_to(target)))))
        elif ext == ".pdf":
            target = expanded / f"pdf_{pdf_index}"
            target.mkdir()
            pdf_index += 1
            document = fitz.open(source)
            try:
                for number, page in enumerate(document):
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    path = target / f"{number + 1:06d}.png"
                    pixmap.save(path)
                    images.append(path)
            finally:
                document.close()
    return images


def comic_info(form) -> bytes:
    root = ET.Element("ComicInfo")
    fields = {
        "Title": form.get("title", "").strip(),
        "Series": form.get("series", "").strip(),
        "Number": form.get("number", "").strip(),
        "Writer": form.get("writer", "").strip(),
        "Genre": form.get("genre", "").strip(),
        "Summary": form.get("summary", "").strip(),
        "Manga": "YesAndRightToLeft" if form.get("direction") == "rtl" else "No",
    }
    for name, value in fields.items():
        if value:
            ET.SubElement(root, name).text = value
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _webtoon_pages(image: Image.Image, width: int, height: int) -> list[Image.Image]:
    """Cut a vertical strip into screen-shaped pages, padding the last page."""
    if not width or not height:
        raise ValueError("Choose an e-reader preset or enter a width and height for Webtoon mode.")
    # Crop in source pixels before resizing so no part of the artwork is stretched.
    slice_height = max(1, round(image.width * height / width))
    pages: list[Image.Image] = []
    for top in range(0, image.height, slice_height):
        crop = image.crop((0, top, image.width, min(top + slice_height, image.height)))
        crop.thumbnail((width, height), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (width, height), "white")
        # Keep the reading flow anchored at the top; center horizontally if needed.
        canvas.paste(crop, ((width - crop.width) // 2, 0))
        crop.close()
        pages.append(canvas)
    image.close()
    return pages


def process_image(path: Path, form) -> list[Image.Image]:
    with Image.open(path) as opened:
        opened.seek(0)
        image = ImageOps.exif_transpose(opened).convert("RGB")

    max_width = max(0, int(form.get("max_width", "0") or 0))
    max_height = max(0, int(form.get("max_height", "0") or 0))
    if form.get("layout") == "webtoon":
        return _webtoon_pages(image, max_width, max_height)

    pages = [image]
    split = form.get("split_spreads") == "on"
    threshold = float(form.get("spread_ratio", "1.35"))
    if split and image.width / max(image.height, 1) >= threshold:
        middle = image.width // 2
        left = image.crop((0, 0, middle, image.height))
        right = image.crop((middle, 0, image.width, image.height))
        pages = [right, left] if form.get("direction") == "rtl" else [left, right]
        image.close()

    if max_width or max_height:
        bound = (max_width or 100000, max_height or 100000)
        for page in pages:
            page.thumbnail(bound, Image.Resampling.LANCZOS)
    return pages


def make_cbz(input_dir: Path, work_dir: Path, form) -> tuple[Path, int]:
    sources = collect_images(input_dir, work_dir)
    if not sources:
        raise ValueError("No supported images were found in the selected files.")

    output = work_dir / "output.cbz"
    output_format = form.get("format", "jpeg")
    extension = {"jpeg": "jpg", "png": "png", "webp": "webp"}.get(output_format, "jpg")
    quality = max(1, min(100, int(form.get("quality", "88"))))
    page_number = 0

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for source in sources:
            try:
                pages = process_image(source, form)
            except (UnidentifiedImageError, OSError):
                continue
            for page in pages:
                page_number += 1
                buffer = io.BytesIO()
                options = {}
                if output_format in {"jpeg", "webp"}:
                    options.update(quality=quality, optimize=True)
                page.save(buffer, format=output_format.upper(), **options)
                archive.writestr(f"{page_number:06d}.{extension}", buffer.getvalue())
                page.close()
        if page_number == 0:
            raise ValueError("The selected files did not contain readable images.")
        archive.writestr("ComicInfo.xml", comic_info(form))
    return output, page_number


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.post("/convert")
def convert():
    uploads = request.files.getlist("files")
    if not uploads or not any(item.filename for item in uploads):
        return jsonify(error="Choose at least one file."), 400

    temp_root = Path(tempfile.mkdtemp(prefix="manga_converter_"))
    input_dir = temp_root / "input"
    input_dir.mkdir()
    try:
        saved = 0
        for index, upload in enumerate(uploads):
            if not upload.filename:
                continue
            original = Path(upload.filename)
            if original.suffix.lower() not in ALLOWED_EXTENSIONS:
                continue
            filename = secure_filename(original.name) or f"file_{index}{original.suffix.lower()}"
            upload.save(input_dir / f"{index:06d}_{filename}")
            saved += 1
        if not saved:
            raise ValueError("Supported files: JPG, PNG, WebP, GIF, TIFF, BMP, PDF, ZIP and CBZ.")

        output, count = make_cbz(input_dir, temp_root, request.form)
        requested = secure_filename(request.form.get("output_name", "manga").strip()) or "manga"
        if not requested.lower().endswith(".cbz"):
            requested += ".cbz"

        @after_this_request
        def cleanup(response):
            response.call_on_close(lambda: shutil.rmtree(temp_root, ignore_errors=True))
            return response

        response = send_file(output, as_attachment=True, download_name=requested, mimetype="application/vnd.comicbook+zip")
        response.headers["X-Page-Count"] = str(count)
        return response
    except (ValueError, zipfile.BadZipFile, fitz.FileDataError) as error:
        shutil.rmtree(temp_root, ignore_errors=True)
        return jsonify(error=str(error)), 400
    except Exception:
        shutil.rmtree(temp_root, ignore_errors=True)
        app.logger.exception("Conversion failed")
        return jsonify(error="Conversion failed. Check the files and try again."), 500


@app.errorhandler(413)
def too_large(_error):
    return jsonify(error="Upload is too large. The combined limit is 2 GB."), 413


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    host = os.environ.get("HOST", "127.0.0.1")
    app.run(host=host, port=port, threaded=True)
