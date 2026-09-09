# src/multimodal_parser.py
"""
HEXA Multimodal File Ingestion, OCR & Table Extraction Pipeline.

Extracts text, tables, formulas, and structural metadata from:
- PDFs: pypdf text extraction + table parsing
- Word (.docx): python-docx headings, paragraphs, and tables
- Excel (.xlsx): openpyxl sheet cells, formulas, and markdown table conversion
- PowerPoint (.pptx): python-pptx slide text, notes, and shape tables
- Code Files (.py, .c, .cpp, .java, .js, .sh, .bash, .sql, .json, .xml, .html): Source code tokenization
- Images & Scanned Docs (.png, .jpg, .jpeg, .tiff, .bmp): On-device OCR (pytesseract / OCR models)
"""

import os
import re
import io
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("hexa.multimodal_parser")

# Programming file extensions supported for direct text tokenization
CODE_EXTENSIONS = {
    ".py", ".c", ".cpp", ".h", ".hpp", ".cs", ".java", ".js", ".ts", ".jsx", ".tsx",
    ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd", ".sql", ".json", ".xml", ".yaml",
    ".yml", ".html", ".css", ".md", ".rst", ".nix", ".go", ".rs", ".php", ".rb"
}

def extract_pdf(file_path: str) -> Dict[str, Any]:
    """Extract text, page count, and structural tables from a PDF using pypdf."""
    extracted_text = []
    tables = []
    try:
        import pypdf
        reader = pypdf.PdfReader(file_path)
        page_count = len(reader.pages)
        
        for idx, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            extracted_text.append(f"--- Page {idx + 1} ---\n{page_text}")
            
            # Simple heuristic for table detection in PDF text (lines with multiple delimiters)
            lines = page_text.splitlines()
            table_lines = [l for l in lines if "|" in l or "  " in l]
            if len(table_lines) >= 2:
                tables.append({
                    "page": idx + 1,
                    "content": "\n".join(table_lines)
                })
                
        return {
            "format": "pdf",
            "page_count": page_count,
            "text": "\n\n".join(extracted_text),
            "tables": tables,
            "success": True
        }
    except Exception as e:
        logger.error(f"Error parsing PDF {file_path}: {e}")
        return {"format": "pdf", "text": "", "tables": [], "success": False, "error": str(e)}


def extract_docx(file_path: str) -> Dict[str, Any]:
    """Extract paragraphs, headings, and tables from a Word (.docx) file using python-docx."""
    extracted_parts = []
    extracted_tables = []
    try:
        import docx
        doc = docx.Document(file_path)
        
        for p in doc.paragraphs:
            if p.text.strip():
                if p.style and p.style.name.startswith("Heading"):
                    extracted_parts.append(f"\n### {p.text.strip()}\n")
                else:
                    extracted_parts.append(p.text.strip())
                    
        # Table Extraction
        for t_idx, table in enumerate(doc.tables):
            table_data = []
            for row in table.rows:
                row_cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                table_data.append("| " + " | ".join(row_cells) + " |")
            if table_data:
                md_table = "\n".join(table_data)
                extracted_tables.append({"table_index": t_idx + 1, "markdown": md_table})
                extracted_parts.append(f"\n**[Table {t_idx + 1}]**\n{md_table}\n")
                
        return {
            "format": "docx",
            "text": "\n\n".join(extracted_parts),
            "tables": extracted_tables,
            "success": True
        }
    except Exception as e:
        logger.error(f"Error parsing DOCX {file_path}: {e}")
        return {"format": "docx", "text": "", "tables": [], "success": False, "error": str(e)}


def extract_xlsx(file_path: str) -> Dict[str, Any]:
    """Extract sheets, cell values, formulas, and tables from Excel (.xlsx) using openpyxl."""
    extracted_sheets = []
    extracted_tables = []
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, data_only=False)
        
        for sheetname in wb.sheetnames:
            ws = wb[sheetname]
            sheet_rows = []
            for row in ws.iter_rows(values_only=True):
                row_vals = [str(val) if val is not None else "" for val in row]
                if any(row_vals):  # Skip empty rows
                    sheet_rows.append("| " + " | ".join(row_vals) + " |")
                    
            if sheet_rows:
                md_table = f"### Sheet: {sheetname}\n" + "\n".join(sheet_rows)
                extracted_sheets.append(md_table)
                extracted_tables.append({"sheet": sheetname, "markdown": md_table})
                
        return {
            "format": "xlsx",
            "text": "\n\n".join(extracted_sheets),
            "tables": extracted_tables,
            "success": True
        }
    except Exception as e:
        logger.error(f"Error parsing XLSX {file_path}: {e}")
        return {"format": "xlsx", "text": "", "tables": [], "success": False, "error": str(e)}


def extract_pptx(file_path: str) -> Dict[str, Any]:
    """Extract slide text, shapes, and tables from PowerPoint (.pptx) using python-pptx."""
    slide_texts = []
    extracted_tables = []
    try:
        from pptx import Presentation
        prs = Presentation(file_path)
        
        for idx, slide in enumerate(prs.slides):
            slide_content = [f"--- Slide {idx + 1} ---"]
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        text = paragraph.text.strip()
                        if text:
                            slide_content.append(text)
                elif shape.has_table:
                    table_rows = []
                    for row in shape.table.rows:
                        row_text = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                        table_rows.append("| " + " | ".join(row_text) + " |")
                    if table_rows:
                        md_table = "\n".join(table_rows)
                        extracted_tables.append({"slide": idx + 1, "markdown": md_table})
                        slide_content.append(f"\n**[Slide {idx + 1} Table]**\n{md_table}\n")
                        
            slide_texts.append("\n".join(slide_content))
            
        return {
            "format": "pptx",
            "slide_count": len(prs.slides),
            "text": "\n\n".join(slide_texts),
            "tables": extracted_tables,
            "success": True
        }
    except Exception as e:
        logger.error(f"Error parsing PPTX {file_path}: {e}")
        return {"format": "pptx", "text": "", "tables": [], "success": False, "error": str(e)}


def extract_code_file(file_path: str) -> Dict[str, Any]:
    """Extract source code, structure, and line count for programming files."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            code_text = f.read()
            
        ext = os.path.splitext(file_path)[1].lower().lstrip(".")
        formatted_text = f"```{ext}\n// File: {os.path.basename(file_path)}\n{code_text}\n```"
        
        return {
            "format": "code",
            "extension": ext,
            "text": formatted_text,
            "line_count": len(code_text.splitlines()),
            "success": True
        }
    except Exception as e:
        logger.error(f"Error reading code file {file_path}: {e}")
        return {"format": "code", "text": "", "success": False, "error": str(e)}


def extract_image_ocr(file_path: str) -> Dict[str, Any]:
    """Extract text and tabular structures from images/scanned blueprints via local OCR."""
    try:
        import pytesseract
        from PIL import Image
        
        img = Image.open(file_path)
        ocr_text = pytesseract.image_to_string(img)
        
        return {
            "format": "image_ocr",
            "text": f"--- OCR Extracted Text ({os.path.basename(file_path)}) ---\n{ocr_text.strip()}",
            "tables": [],
            "success": True
        }
    except Exception as e:
        logger.warning(f"pytesseract OCR not available or failed for {file_path}: {e}")
        return {
            "format": "image_ocr",
            "text": f"[Multimodal Image Attached: {os.path.basename(file_path)} - Ready for Vision LLM]",
            "tables": [],
            "success": False,
            "error": str(e)
        }


def parse_multimodal_file(file_path: str) -> Dict[str, Any]:
    """
    Unified entry point for multimodal file parsing & table extraction.
    Automatically detects format based on extension and returns structured tokenizable content.
    """
    if not os.path.exists(file_path):
        return {"success": False, "error": f"File not found: {file_path}"}
        
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == ".pdf":
        return extract_pdf(file_path)
    elif ext in (".docx", ".doc"):
        return extract_docx(file_path)
    elif ext in (".xlsx", ".xls"):
        return extract_xlsx(file_path)
    elif ext in (".pptx", ".ppt"):
        return extract_pptx(file_path)
    elif ext in CODE_EXTENSIONS:
        return extract_code_file(file_path)
    elif ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"):
        return extract_image_ocr(file_path)
    else:
        # Fallback to plain text read
        return extract_code_file(file_path)
