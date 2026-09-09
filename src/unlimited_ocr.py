# src/unlimited_ocr.py
"""
Unlimited-OCR integration — Baidu's 3B vision-language OCR model.
https://huggingface.co/baidu/Unlimited-OCR  (MIT License)

This module provides a drop-in OCR backend for images and PDFs.
It is used automatically when:
  - A user uploads an image in chat and asks for text extraction / OCR
  - The intent router classifies a request as 'vision_ocr'
  - qwen3-vl is unavailable or the user explicitly requests document OCR

Requirements (NVIDIA GPU with CUDA):
  pip install torch torchvision transformers Pillow einops addict easydict psutil

The model is downloaded on first use (~6GB) into the HuggingFace cache.
VRAM requirement: ~6GB (BF16) — fits on RTX 5050 8GB but leaves little headroom.

Usage pattern:
  from src.unlimited_ocr import ocr_image, ocr_available
  if ocr_available():
      text = ocr_image("path/to/image.png")
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger("hexa.unlimited_ocr")

MODEL_ID = "baidu/Unlimited-OCR"
_model = None
_tokenizer = None
_load_error: Optional[str] = None
_load_attempted = False


def ocr_available() -> bool:
    """Return True if Unlimited-OCR can be loaded (CUDA + dependencies present)."""
    try:
        import torch
        if not torch.cuda.is_available():
            return False
        import transformers  # noqa: F401
        import einops  # noqa: F401
        return True
    except ImportError:
        return False


def _load_model():
    """Load model and tokenizer lazily on first use."""
    global _model, _tokenizer, _load_error, _load_attempted
    if _load_attempted:
        return _model is not None

    _load_attempted = True
    try:
        import torch
        from transformers import AutoModel, AutoTokenizer

        if not torch.cuda.is_available():
            _load_error = "Unlimited-OCR requires a CUDA-capable NVIDIA GPU."
            logger.warning(_load_error)
            return False

        logger.info("Loading Unlimited-OCR model (%s) — first load downloads ~6GB...", MODEL_ID)
        _tokenizer = AutoTokenizer.from_pretrained(
            MODEL_ID,
            trust_remote_code=True,
        )
        _model = AutoModel.from_pretrained(
            MODEL_ID,
            trust_remote_code=True,
            use_safetensors=True,
            torch_dtype=torch.bfloat16,
        )
        _model = _model.eval().cuda()
        logger.info("Unlimited-OCR model loaded successfully on GPU: %s", torch.cuda.get_device_name(0))
        return True

    except Exception as e:
        _load_error = f"Failed to load Unlimited-OCR: {e}"
        logger.error(_load_error)
        return False


def ocr_image(image_path: str, mode: str = "gundam") -> str:
    """
    Extract text from a single image using Unlimited-OCR.

    Args:
        image_path: Path to the image file (PNG, JPEG, etc.)
        mode: 'gundam' (faster, 640px crop) or 'base' (higher quality, 1024px)

    Returns:
        Extracted text as a string, or error message.
    """
    if not ocr_available():
        return "[Unlimited-OCR unavailable: CUDA GPU or dependencies missing. Run: pip install torch transformers einops addict easydict]"

    if not _load_model():
        return f"[Unlimited-OCR load failed: {_load_error}]"

    try:
        import tempfile as _tmp
        output_dir = _tmp.mkdtemp(prefix="hexa_ocr_")

        # Map mode to parameters
        if mode == "gundam":
            kwargs = dict(base_size=1024, image_size=640, crop_mode=True)
        else:
            kwargs = dict(base_size=1024, image_size=1024, crop_mode=False)

        _model.infer(
            _tokenizer,
            prompt="<image>document parsing.",
            image_file=image_path,
            output_path=output_dir,
            max_length=32768,
            no_repeat_ngram_size=35,
            ngram_window=128,
            save_results=True,
            **kwargs,
        )

        # Read the output text file
        out_files = list(Path(output_dir).glob("*.txt")) + list(Path(output_dir).glob("*.md"))
        if out_files:
            text = out_files[0].read_text(encoding="utf-8", errors="replace").strip()
            text = _remove_det_markers(text)
            logger.info("Unlimited-OCR extracted %d chars from %s", len(text), os.path.basename(image_path))
            return text
        else:
            return "[Unlimited-OCR: no output text found]"

    except Exception as e:
        logger.error("Unlimited-OCR inference failed for %s: %s", image_path, e)
        return f"[Unlimited-OCR error: {e}]"


def ocr_multi_image(image_paths: list[str]) -> str:
    """
    Extract text from multiple images (e.g. PDF pages) using Unlimited-OCR.

    Args:
        image_paths: List of paths to page images in order.

    Returns:
        Combined extracted text.
    """
    if not ocr_available():
        return "[Unlimited-OCR unavailable: CUDA GPU or dependencies missing]"

    if not _load_model():
        return f"[Unlimited-OCR load failed: {_load_error}]"

    try:
        import tempfile as _tmp
        output_dir = _tmp.mkdtemp(prefix="hexa_ocr_multi_")

        _model.infer_multi(
            _tokenizer,
            prompt="<image>Multi page parsing.",
            image_files=image_paths,
            output_path=output_dir,
            image_size=1024,
            max_length=32768,
            no_repeat_ngram_size=35,
            ngram_window=1024,
            save_results=True,
        )

        out_files = sorted(Path(output_dir).glob("*.txt")) + sorted(Path(output_dir).glob("*.md"))
        if out_files:
            combined = "\n\n".join(
                f.read_text(encoding="utf-8", errors="replace").strip()
                for f in out_files
            )
            combined = _remove_det_markers(combined)
            logger.info("Unlimited-OCR extracted %d chars from %d pages", len(combined), len(image_paths))
            return combined
        return "[Unlimited-OCR: no output text found]"

    except Exception as e:
        logger.error("Unlimited-OCR multi-page inference failed: %s", e)
        return f"[Unlimited-OCR error: {e}]"


def ocr_pdf(pdf_path: str) -> str:
    """
    Extract text from a PDF by converting pages to images and running Unlimited-OCR.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Extracted text from all pages.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return "[PDF OCR requires PyMuPDF: pip install PyMuPDF]"

    try:
        doc = fitz.open(pdf_path)
        tmp_dir = tempfile.mkdtemp(prefix="hexa_pdf_ocr_")
        mat = fitz.Matrix(300 / 72, 300 / 72)  # 300 DPI
        page_paths = []
        for i, page in enumerate(doc):
            out_path = os.path.join(tmp_dir, f"page_{i+1:04d}.png")
            page.get_pixmap(matrix=mat).save(out_path)
            page_paths.append(out_path)
        doc.close()
        logger.info("PDF converted to %d page images for OCR", len(page_paths))
        return ocr_multi_image(page_paths)
    except Exception as e:
        logger.error("PDF to images conversion failed: %s", e)
        return f"[PDF OCR error: {e}]"


def _remove_det_markers(raw: str) -> str:
    """Strip <|det|>...<|/det|> detection markers from Unlimited-OCR output."""
    import re
    DET_RE = re.compile(r"<\|det\|>([^<\s]+)(?:\s*\[[^\]]*\])?\s*<\|/det\|>(.*)", re.DOTALL)
    blocks = []
    cur = None
    for line in raw.splitlines():
        line = line.rstrip()
        if not line:
            continue
        m = DET_RE.match(line)
        if m:
            category = m.group(1).strip()
            content = m.group(2).strip()
            if category == "image":
                continue
            if cur is not None:
                blocks.append(cur)
            cur = [content] if content else []
            continue
        if cur is None:
            cur = []
        cur.append(line)
    if cur is not None:
        blocks.append(cur)
    return "\n\n".join("\n".join(b) for b in blocks if b).strip()


def install_requirements() -> str:
    """Install Unlimited-OCR dependencies. Returns status message."""
    import subprocess, sys
    packages = [
        "torch", "torchvision", "transformers==4.57.1",
        "einops", "addict", "easydict", "psutil",
    ]
    logger.info("Installing Unlimited-OCR dependencies: %s", packages)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install"] + packages,
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            return "Unlimited-OCR dependencies installed successfully. Restart the app."
        return f"Install failed:\n{result.stderr[-500:]}"
    except Exception as e:
        return f"Install error: {e}"
