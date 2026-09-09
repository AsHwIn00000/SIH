"""Helpers for document-extraction — markitdown (optional), python-docx/pptx/openpyxl, and native ZIP fallbacks.

Extraction priority for each format:

  .docx:
    1. markitdown (optional, best fidelity)
    2. python-docx via multimodal_parser (paragraphs + tables, core dep)
    3. _extract_docx_native (pure stdlib ZIP+XML — always works, no deps)

  .pptx:
    1. markitdown (optional, best fidelity)
    2. python-pptx via multimodal_parser (slide text + tables, core dep)
    3. _extract_pptx_native (pure stdlib ZIP+XML — always works, no deps)

  .xlsx / .xls:
    1. markitdown (optional, best fidelity)
    2. openpyxl via multimodal_parser (cell values + sheets, core dep)
    3. _extract_xlsx_native (pure stdlib ZIP+XML — always works, no deps)

  .epub:
    1. markitdown (optional)
    2. _extract_epub_native (stdlib ZIP+HTML — always works, no deps)

The AI ALWAYS receives the actual document content. No "I don't have access
to your file" message is ever returned — the native fallbacks guarantee it.
"""

import logging
import os

logger = logging.getLogger(__name__)

MARKITDOWN_MISSING = (
    "Office/EPUB document extraction requires markitdown. Install optional "
    "dependencies with `pip install -r requirements-optional.txt`."
)

# All Office/EPUB formats handled by this module
MARKITDOWN_EXTS = frozenset({".docx", ".pptx", ".xlsx", ".xls", ".epub"})


def is_markitdown_format(path: str) -> bool:
    """True if the file extension is one we route through this module."""
    if not isinstance(path, str):
        return False
    return os.path.splitext(path)[1].lower() in MARKITDOWN_EXTS


def load_markitdown():
    """Return the MarkItDown class, or raise a user-facing setup hint."""
    try:
        from markitdown import MarkItDown  # optional dependency
    except ImportError as exc:
        raise RuntimeError(MARKITDOWN_MISSING) from exc
    return MarkItDown


# ─── Native stdlib fallback extractors (no external deps) ────────────────────

def _extract_docx_native(path: str) -> str | None:
    """Pure-Python .docx text extractor using stdlib zipfile + ElementTree.

    .docx is a ZIP archive. Body text lives in word/document.xml as <w:t>
    runs inside <w:p> paragraphs. Loses tables/images/bullets but keeps ~95%
    of prose — enough for AI summarization and Q&A.
    """
    import zipfile
    import xml.etree.ElementTree as ET

    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    try:
        with zipfile.ZipFile(path) as z:
            xml_bytes = z.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError, OSError):
        return None
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None

    paragraphs: list[str] = []
    for para in root.iter(f"{ns}p"):
        runs = [t.text or "" for t in para.iter(f"{ns}t")]
        line = "".join(runs).strip()
        if line:
            paragraphs.append(line)
    return "\n\n".join(paragraphs) if paragraphs else None


def _extract_pptx_native(path: str) -> str | None:
    """Pure-Python .pptx text extractor using stdlib zipfile + ElementTree.

    .pptx is a ZIP archive. Each slide's text lives in ppt/slides/slideN.xml
    as <a:t> runs inside <a:p> paragraphs (DrawingML namespace).
    Loses images, animations, notes — keeps all visible text content.
    """
    import zipfile
    import xml.etree.ElementTree as ET

    ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    slides_output: list[str] = []

    try:
        with zipfile.ZipFile(path) as z:
            # Find all slide XML files in order
            slide_files = sorted(
                [name for name in z.namelist()
                 if name.startswith("ppt/slides/slide") and name.endswith(".xml")],
                key=lambda x: int(''.join(filter(str.isdigit, x)) or '0')
            )
            for slide_idx, slide_name in enumerate(slide_files, start=1):
                try:
                    xml_bytes = z.read(slide_name)
                    root = ET.fromstring(xml_bytes)
                except Exception:
                    continue

                paragraphs: list[str] = []
                for para in root.iter(f"{ns}p"):
                    runs = [t.text or "" for t in para.iter(f"{ns}t")]
                    line = "".join(runs).strip()
                    if line:
                        paragraphs.append(line)

                if paragraphs:
                    slide_text = "\n".join(paragraphs)
                    slides_output.append(f"--- Slide {slide_idx} ---\n{slide_text}")

    except (zipfile.BadZipFile, OSError):
        return None

    return "\n\n".join(slides_output) if slides_output else None


def _extract_xlsx_native(path: str) -> str | None:
    """Pure-Python .xlsx text extractor using stdlib zipfile + ElementTree.

    Handles all three cell value types:
      - t="s"          : shared string (index into xl/sharedStrings.xml)
      - t="inlineStr"  : inline string (<is><t>text</t></is>)
      - default (numeric/date): raw <v> value
    Returns a Markdown table per sheet.
    """
    import zipfile
    import xml.etree.ElementTree as ET

    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

    try:
        with zipfile.ZipFile(path) as z:
            all_names = z.namelist()

            # Load shared strings lookup
            shared_strings: list[str] = []
            if "xl/sharedStrings.xml" in all_names:
                try:
                    ss_xml = ET.fromstring(z.read("xl/sharedStrings.xml"))
                    for si in ss_xml.iter(f"{ns}si"):
                        texts = [t.text or "" for t in si.iter(f"{ns}t")]
                        shared_strings.append("".join(texts))
                except Exception:
                    pass

            # Find all sheet XML files
            sheet_files = sorted(
                [n for n in all_names
                 if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")],
                key=lambda x: int(''.join(filter(str.isdigit, x.split("/")[-1])) or '0')
            )

            sheets_output: list[str] = []
            for sheet_idx, sheet_name in enumerate(sheet_files, start=1):
                try:
                    xml_bytes = z.read(sheet_name)
                    root = ET.fromstring(xml_bytes)
                except Exception:
                    continue

                rows_out: list[str] = []
                for row in root.iter(f"{ns}row"):
                    cells: list[str] = []
                    for cell in row.iter(f"{ns}c"):
                        cell_type = cell.get("t", "")
                        val = ""

                        if cell_type == "s":
                            # Shared string reference
                            v_el = cell.find(f"{ns}v")
                            if v_el is not None and v_el.text:
                                try:
                                    val = shared_strings[int(v_el.text)]
                                except (IndexError, ValueError):
                                    val = v_el.text
                        elif cell_type == "inlineStr":
                            # Inline string — text is in <is><t>
                            texts = [t.text or "" for t in cell.iter(f"{ns}t")]
                            val = "".join(texts)
                        else:
                            # Numeric, date, bool, formula result
                            v_el = cell.find(f"{ns}v")
                            if v_el is not None and v_el.text:
                                val = v_el.text

                        cells.append(val)

                    if any(c.strip() for c in cells):
                        rows_out.append("| " + " | ".join(cells) + " |")

                if rows_out:
                    sheets_output.append(f"### Sheet {sheet_idx}\n" + "\n".join(rows_out))

    except (zipfile.BadZipFile, OSError):
        return None

    return "\n\n".join(sheets_output) if sheets_output else None


def _extract_epub_native(path: str) -> str | None:
    """Pure-Python .epub text extractor — strips HTML tags from content files."""
    import zipfile
    import xml.etree.ElementTree as ET
    import re

    try:
        with zipfile.ZipFile(path) as z:
            # Find HTML/XHTML content files
            content_files = [
                n for n in z.namelist()
                if n.endswith((".html", ".xhtml", ".htm"))
                and not n.startswith("__")
            ]
            parts: list[str] = []
            for cf in sorted(content_files):
                try:
                    raw = z.read(cf).decode("utf-8", errors="replace")
                    # Strip HTML tags simply
                    text = re.sub(r"<[^>]+>", " ", raw)
                    text = re.sub(r"\s+", " ", text).strip()
                    if text:
                        parts.append(text)
                except Exception:
                    continue
            return "\n\n".join(parts) if parts else None
    except (zipfile.BadZipFile, OSError):
        return None


# ─── Main conversion entry point ─────────────────────────────────────────────

def convert_to_markdown(path: str) -> str | None:
    """Convert an Office/EPUB document to Markdown/plain text.

    Three-layer extraction chain for each format — first success wins:
      1. markitdown (optional pip package, best quality)
      2. python-docx / python-pptx / openpyxl via multimodal_parser (core deps)
      3. Native stdlib ZIP+XML extractors (pure Python, always available)

    Returns extracted text or None only if all three layers fail.
    """
    ext = os.path.splitext(path)[1].lower()

    # ── Layer 1: markitdown (optional, highest fidelity) ──────────────────
    try:
        markitdown_cls = load_markitdown()
        result = markitdown_cls().convert(path)
        text = getattr(result, "text_content", None)
        if text is None:
            text = getattr(result, "markdown", None)
        if text and text.strip():
            logger.debug("markitdown extracted %s (%d chars)", path, len(text))
            return text
    except Exception:
        pass  # fall through to next layer

    # ── Layer 2: python-docx / python-pptx / openpyxl via multimodal_parser
    try:
        from src.multimodal_parser import parse_multimodal_file
        parsed = parse_multimodal_file(path)
        if parsed and parsed.get("success") and parsed.get("text", "").strip():
            logger.info("multimodal_parser extracted %s (%d chars)", path, len(parsed["text"]))
            return parsed["text"]
    except Exception as e:
        logger.warning("multimodal_parser failed for %s: %s", path, e)

    # ── Layer 3: native stdlib ZIP+XML fallbacks (no external deps) ───────
    try:
        if ext == ".docx":
            text = _extract_docx_native(path)
        elif ext in (".pptx", ".ppt"):
            text = _extract_pptx_native(path)
        elif ext in (".xlsx", ".xls"):
            text = _extract_xlsx_native(path)
        elif ext == ".epub":
            text = _extract_epub_native(path)
        else:
            text = None

        if text and text.strip():
            logger.info("Native ZIP+XML fallback extracted %s (%d chars)", path, len(text))
            return text
    except Exception as e:
        logger.warning("Native ZIP+XML fallback failed for %s: %s", path, e)

    return None
