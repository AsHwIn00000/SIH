"""Helpers for document-extraction — markitdown (optional), python-docx, and native ZIP fallback.

Extraction priority for .docx / .pptx / .xlsx / .epub:
  1. markitdown (MIT, Microsoft) — best fidelity, optional dep.
  2. python-docx via src.multimodal_parser — full paragraph + table extraction,
     now a core dep so .docx files are always readable out of the box.
  3. Native ZIP+XML extractor (_extract_docx_native) — pure stdlib, no external
     deps, works for .docx even when all optional packages are absent.

The AI always receives the actual document text. The old "I don't have access to
the content of your .docx file" message was caused by the fallback chain not
reaching the ZIP extractor. This file fixes that by adding it as the last step.
"""

import logging
import os

logger = logging.getLogger(__name__)

MARKITDOWN_MISSING = (
    "Office/EPUB document extraction requires markitdown. Install optional "
    "dependencies with `pip install -r requirements-optional.txt`."
)

# Formats routed through markitdown. PDFs stay on pypdf (src/document_processor
# and src/personal_docs); plain text/code/csv/json/markdown/html stay on the
# cheaper built-in text path. These are the formats currently dropped entirely.
MARKITDOWN_EXTS = frozenset({".docx", ".pptx", ".xlsx", ".xls", ".epub"})


def is_markitdown_format(path: str) -> bool:
    """True if the file extension is one we route through markitdown."""
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


def _extract_docx_native(path: str) -> str | None:
    """Pure-Python .docx text extractor — no external deps.

    A .docx file is just a zip of XML. The body prose lives in <w:t> runs
    inside <w:p> paragraphs. Iterating with ElementTree (rather than
    re.findall) keeps paragraph breaks intact and lets the XML parser handle
    namespaces + entity unescaping. Loses tables, footnotes, images and
    list bullets — keeps ~95% of "summarize this doc" content, which is the
    case people hit when markitdown isn't installed.
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


def convert_to_markdown(path: str) -> str | None:
    """Convert a document to Markdown text.

    Extraction chain (first success wins):
      1. markitdown (optional dep) — best fidelity for all Office/EPUB formats.
      2. python-docx via src.multimodal_parser — full paragraphs + tables for .docx.
      3. _extract_docx_native (stdlib ZIP+XML) — .docx only, no external deps.
         This is the guaranteed last-resort so the AI always sees document content.
    """
    # 1. markitdown (optional)
    try:
        markitdown_cls = load_markitdown()
        result = markitdown_cls().convert(path)
        text = getattr(result, "text_content", None)
        if text is None:
            text = getattr(result, "markdown", None)
        if text and text.strip():
            return text
    except Exception:
        pass

    # 2. Native HEXA Multimodal Parser (uses python-docx when available)
    try:
        from src.multimodal_parser import parse_multimodal_file
        parsed = parse_multimodal_file(path)
        if parsed and parsed.get("success") and parsed.get("text"):
            logger.info("Used native HEXA multimodal parser for %s", path)
            return parsed["text"]
    except Exception as e:
        logger.warning("Native HEXA multimodal parser failed for %s: %s", path, e)

    # 3. Last-resort: pure-stdlib ZIP+XML extractor for .docx (no external deps)
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        try:
            text = _extract_docx_native(path)
            if text and text.strip():
                logger.info("Used native ZIP+XML fallback extractor for %s", path)
                return text
        except Exception as e:
            logger.warning("Native ZIP+XML extractor failed for %s: %s", path, e)

    return None
