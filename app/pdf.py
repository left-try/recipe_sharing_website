from __future__ import annotations

from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from xml.sax.saxutils import escape

import requests
from flask import current_app
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

from .ingredient_compute import compute_recipe_ingredients, ingredient_line_text
from .utils import render_markdown, slugify


# Generate a PDF for a recipe, optionally adjusting ingredient quantities for a target servings count and measurement system (metric/us/none)
def build_recipe_pdf(recipe, target_servings=None, unit_mode: str = "original"):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
        title=recipe.title,
    )

    styles = getSampleStyleSheet()
    body_style = styles["BodyText"]
    body_style.spaceAfter = 6
    section_style = styles["Heading2"]
    meta_style = ParagraphStyle(
        "RecipeMeta",
        parent=body_style,
        fontSize=10,
        leading=13,
        textColor="#555555",
        spaceAfter=10,
    )

    story = [
        Paragraph(escape(recipe.title), styles["Title"]),
        Paragraph(f"By {escape(recipe.author.username)}", meta_style),
    ]

    image_flowable = _build_recipe_image_flowable(recipe)
    if image_flowable is not None:
        story.extend([image_flowable, Spacer(1, 12)])

    meta_parts = []
    if recipe.category:
        meta_parts.append(f"Category: {escape(recipe.category.name)}")
    meta_parts.append(f"Prep: {recipe.prep_minutes} min")
    meta_parts.append(f"Cook: {recipe.cook_minutes} min")
    if unit_mode not in ("original", "metric", "us"):
        unit_mode = "original"
    computed = compute_recipe_ingredients(recipe, target_servings=target_servings, mode=unit_mode)
    meta_parts.append(f"Servings: {recipe.servings}")
    if computed["scaleFactor"] != 1.0 or unit_mode != "original":
        meta_parts.append(
            f"Shown: {computed['targetServings']} servings, {unit_mode} units"
        )
    meta_parts.append(f"Difficulty: {escape(recipe.difficulty)}")
    story.append(Paragraph(" | ".join(meta_parts), meta_style))

    if recipe.description:
        story.extend(
            [
                Paragraph("Description", section_style),
                *_markdown_flowables(recipe.description, body_style),
                Spacer(1, 8),
            ]
        )

    story.append(Paragraph("Ingredients", section_style))
    for ingredient in computed["legacyIngredientLines"] or recipe.ingredients_list():
        story.append(Paragraph(f"- {escape(ingredient)}", body_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Steps", section_style))
    step_num = 0
    structured = recipe.structured_steps()
    for step_idx, step in enumerate(structured):
        if step.get("type") == "video":
            continue

        step_num += 1
        idx = step_num

        if step.get("type") == "content":
            title = str(step.get("title") or "").strip()
            description = str(step.get("description_markdown") or "").strip()
            heading = title or f"Step {idx}"
            story.append(Paragraph(f"{idx}. {escape(heading)}", body_style))
            story.extend(_markdown_flowables(description, body_style))
            comp_step = computed["steps"][step_idx] if step_idx < len(computed["steps"]) else {}
            for item in comp_step.get("ingredients") or []:
                line = ingredient_line_text(
                    str(item.get("displayAmount") or ""),
                    str(item.get("displayUnit") or ""),
                    str(item.get("name") or ""),
                )
                note = item.get("note")
                if note:
                    line = f"{line} ({note})"
                if line:
                    story.append(Paragraph(f"- {escape(line)}", body_style))
            story.append(Spacer(1, 6))
            continue

        image_flowable = _build_image_flowable(
            _load_image_source(
                str(step.get("image_url") or "").strip(),
                context_label=f"recipe step image for recipe {recipe.id}",
            )
        )
        story.append(Paragraph(f"Step {idx}", body_style))
        if image_flowable is not None:
            story.extend([image_flowable, Spacer(1, 6)])

    if recipe.tags:
        tags = ", ".join(escape(tag.name) for tag in recipe.tags)
        story.extend([Spacer(1, 8), Paragraph(f"Tags: {tags}", meta_style)])

    doc.build(story)
    buffer.seek(0)
    return buffer, f"{slugify(recipe.title) or 'recipe'}.pdf"


# Generate a list of ReportLab flowables from markdown text, using a given style for the text
def _markdown_flowables(text: str, style):
    markup = _markdown_to_reportlab_markup(text)
    if not markup:
        return []
    return [Paragraph(markup, style)]


# Convert markdown text to sanitized ReportLab markup
def _markdown_to_reportlab_markup(text: str) -> str:
    html = str(render_markdown(text or ""))
    parser = _SanitizedHtmlToReportLab()
    parser.feed(html)
    parser.close()
    raw = "".join(parser.parts)
    return _trim_reportlab_markup(raw)


# Trim leading/trailing whitespace and <br/> from a string of ReportLab markup
def _trim_reportlab_markup(s: str) -> str:
    t = s.strip()
    while t.startswith("<br/>"):
        t = t[5:].lstrip()
    while t.endswith("<br/>"):
        t = t[:-5].rstrip()
    return t.strip()


class _SanitizedHtmlToReportLab(HTMLParser):
    """Turn sanitizer HTML (see utils.MARKDOWN_ALLOWED_TAGS) into ReportLab Paragraph markup."""

    _heading_sizes = {"h1": "16", "h2": "14", "h3": "13", "h4": "12", "h5": "11", "h6": "10"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._list_stack: list[str] = []
        self._ol_counts: list[int] = []

    def handle_starttag(self, tag, attrs):
        ad = dict(attrs)
        if tag == "br":
            self.parts.append("<br/>")
        elif tag in ("b", "strong"):
            self.parts.append("<b>")
        elif tag in ("i", "em"):
            self.parts.append("<i>")
        elif tag == "u":
            self.parts.append("<u>")
        elif tag in ("code", "pre"):
            self.parts.append('<font face="Courier">')
        elif tag == "blockquote":
            self.parts.append("<i>")
        elif tag == "a":
            href = (ad.get("href") or "").strip()
            if href:
                safe_href = escape(href, entities={'"': "&quot;"})
                self.parts.append(f'<a href="{safe_href}">')
        elif tag in self._heading_sizes:
            self.parts.append(f'<font size="{self._heading_sizes[tag]}"><b>')
        elif tag == "ul":
            self._list_stack.append("ul")
        elif tag == "ol":
            self._list_stack.append("ol")
            self._ol_counts.append(0)
        elif tag == "li":
            if self._list_stack and self._list_stack[-1] == "ol":
                self._ol_counts[-1] += 1
                n = self._ol_counts[-1]
                self.parts.append(f"<br/>{n}. ")
            else:
                self.parts.append("<br/>• ")

    def handle_endtag(self, tag):
        if tag in ("b", "strong"):
            self.parts.append("</b>")
        elif tag in ("i", "em"):
            self.parts.append("</i>")
        elif tag == "u":
            self.parts.append("</u>")
        elif tag in ("code", "pre"):
            self.parts.append("</font>")
        elif tag == "blockquote":
            self.parts.append("</i>")
        elif tag == "a":
            self.parts.append("</a>")
        elif tag == "p":
            self.parts.append("<br/><br/>")
        elif tag in self._heading_sizes:
            self.parts.append("</b></font><br/>")
        elif tag == "ul":
            if self._list_stack and self._list_stack[-1] == "ul":
                self._list_stack.pop()
        elif tag == "ol":
            if self._list_stack and self._list_stack[-1] == "ol":
                self._list_stack.pop()
                if self._ol_counts:
                    self._ol_counts.pop()

    def handle_startendtag(self, tag, attrs):
        if tag == "br":
            self.parts.append("<br/>")

    def handle_data(self, data):
        self.parts.append(escape(data))


def _build_recipe_image_flowable(recipe):
    return _build_image_flowable(_load_recipe_image_source(recipe), context_label=f"recipe {recipe.id}")


# Build a ReportLab Image flowable from an image source 
def _build_image_flowable(image_source, context_label="image"):
    if image_source is None:
        return None

    try:
        if hasattr(image_source, "seek"):
            image_source.seek(0)
        reader = ImageReader(image_source)
        width, height = reader.getSize()
        max_width = 5.5 * inch
        max_height = 3.5 * inch
        scale = min(max_width / width, max_height / height, 1)
        if hasattr(image_source, "seek"):
            image_source.seek(0)
        return Image(image_source, width=width * scale, height=height * scale)
    except Exception as exc:
        current_app.logger.warning("Could not render %s in PDF: %s", context_label, exc)
        return None


# Load an image for a recipe, trying the recipe's image_url
def _load_recipe_image_source(recipe):
    if recipe.image_url:
        image_source = _load_image_source(recipe.image_url, context_label=f"recipe image for PDF {recipe.id}")
        if image_source is not None:
            return image_source

    if recipe.image_filename:
        upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
        if not upload_folder.is_absolute():
            upload_folder = Path(current_app.root_path).parent / upload_folder
        image_path = upload_folder / recipe.image_filename
        if image_path.exists():
            return str(image_path)

    return None


# Load an image from a URL or local path
def _load_image_source(image_url: str, *, context_label: str):
    parsed = urlparse(image_url)
    if parsed.scheme in ("http", "https"):
        try:
            response = requests.get(image_url, timeout=float(current_app.config.get("FILE_STORAGE_TIMEOUT_SECONDS", 10)))
            response.raise_for_status()
            return BytesIO(response.content)
        except requests.RequestException as exc:
            current_app.logger.warning("Could not fetch %s: %s", context_label, exc)
            return None

    local_path = _resolve_local_image_url(image_url)
    if local_path is not None:
        return local_path
    return None


# Resolve a local image URL to an absolute filesystem path
def _resolve_local_image_url(image_url: str):
    normalized = str(image_url or "").strip()
    static_prefix = "/static/uploads/"
    if not normalized.startswith(static_prefix):
        return None

    filename = normalized[len(static_prefix):].strip("/")
    if not filename:
        return None

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    if not upload_folder.is_absolute():
        upload_folder = Path(current_app.root_path).parent / upload_folder
    image_path = upload_folder / filename
    if image_path.exists():
        return str(image_path)
    return None
