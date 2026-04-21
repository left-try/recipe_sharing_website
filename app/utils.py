import os
import re
import uuid
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

import markdown
from PIL import Image
from flask import current_app
from markupsafe import Markup
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "webm", "ogv"}
MARKDOWN_ALLOWED_TAGS = [
    "a", "abbr", "acronym", "b", "blockquote", "br", "code", "em", "h1", "h2",
    "h3", "h4", "h5", "h6", "i", "li", "ol", "p", "pre", "strong", "ul",
]
MARKDOWN_ALLOWED_ATTRIBUTES = {"a": {"href", "title", "rel"}}
SAFE_LINK_SCHEMES = {"http", "https", "mailto"}

# Internal class to sanitize rendered markdown HTML, allowing only a safe subset of tags and attributes, and escaping all data
class _MarkdownSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag not in MARKDOWN_ALLOWED_TAGS:
            return
        rendered_attrs = []
        allowed_attrs = MARKDOWN_ALLOWED_ATTRIBUTES.get(tag, set())
        for name, value in attrs:
            if name not in allowed_attrs:
                continue
            value = value or ""
            if name == "href":
                parsed = urlparse(value)
                if parsed.scheme and parsed.scheme.lower() not in SAFE_LINK_SCHEMES:
                    continue
            rendered_attrs.append(f' {name}="{escape(value, quote=True)}"')
        self.parts.append(f"<{tag}{''.join(rendered_attrs)}>")

    def handle_startendtag(self, tag, attrs):
        if tag not in MARKDOWN_ALLOWED_TAGS:
            return
        if tag == "br":
            self.parts.append("<br>")
            return
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in MARKDOWN_ALLOWED_TAGS:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(escape(data))

    def handle_entityref(self, name):
        self.parts.append(f"&{name};")

    def handle_charref(self, name):
        self.parts.append(f"&#{name};")

    def get_html(self):
        return "".join(self.parts)

# Generate a URL-friendly slug from a string, or a random string if the result is empty
def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    return s.strip("-") or str(uuid.uuid4())[:8]


# Check if a filename has an allowed image extension
def allowed_file(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


# Check if a filename has an allowed video extension
def allowed_video_file(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_VIDEO_EXTENSIONS


# Save an image file, resizing it to fit within max_size if provided. Returns the new filename
def save_image(file_storage, folder: str, max_size=(1200, 1200)) -> str:
    if not file_storage or file_storage.filename == "":
        return ""
    if not allowed_file(file_storage.filename):
        raise ValueError("Unsupported file type. Use png/jpg/jpeg/webp.")

    filename = secure_filename(file_storage.filename)
    ext = filename.rsplit(".", 1)[1].lower()
    new_name = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(folder, new_name)

    img = Image.open(file_storage)
    img.thumbnail(max_size)
    img.save(path, optimize=True, quality=85)

    return new_name


# Save a video file, returning the new filename
def save_video(file_storage, folder: str) -> str:
    if not file_storage or file_storage.filename == "":
        return ""
    if not allowed_video_file(file_storage.filename):
        raise ValueError("Unsupported video type. Use mp4, webm, or ogv.")

    filename = secure_filename(file_storage.filename)
    ext = filename.rsplit(".", 1)[1].lower()
    new_name = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(folder, new_name)

    file_storage.stream.seek(0)
    with open(path, "wb") as out:
        while True:
            chunk = file_storage.stream.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)

    return new_name


# Delete a file safely, ignoring errors if the file does not exist or cannot be deleted
def delete_file_safely(folder: str, filename: str):
    if not filename:
        return
    path = os.path.join(folder, filename)
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


# Render markdown text to sanitized HTML, allowing only a safe subset of tags and attributes
def render_markdown(text: str) -> Markup:
    rendered = markdown.markdown(text or "", extensions=["extra", "sane_lists", "nl2br"])
    sanitizer = _MarkdownSanitizer()
    sanitizer.feed(rendered)
    sanitizer.close()
    return Markup(sanitizer.get_html())
