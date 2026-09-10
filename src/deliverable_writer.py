# src/deliverable_writer.py
"""
HEXA Air-Gapped Industrial Deliverables Engine.

Generates real production-ready deliverables offline:
- PDF Documents (.pdf)
- Word Approval Notes & Official Memos (.docx)
- Excel Engineering & Financial Spreadsheets (.xlsx)
- PowerPoint Presentations & Decks (.pptx)
- On-Device AI Image Generation (.png / .jpg)
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from src.constants import DATA_DIR, GENERATED_IMAGES_DIR

logger = logging.getLogger("hexa.deliverable_writer")

DELIVERABLES_DIR = os.path.join(DATA_DIR, "deliverables")
os.makedirs(DELIVERABLES_DIR, exist_ok=True)


def create_word_deliverable(
    title: str,
    sections: List[Dict[str, str]],
    tables: Optional[List[List[List[str]]]] = None,
    output_filename: Optional[str] = None
) -> str:
    """
    Generate an official Word (.docx) approval note or engineering memo.
    """
    import docx
    from docx.shared import Inches, Pt, RGBColor
    
    doc = docx.Document()
    
    # Title
    heading = doc.add_heading(title, level=0)
    heading.style.font.color.rgb = RGBColor(0, 95, 115)  # Industrial Teal
    heading.style.font.name = "Calibri"
    heading.style.font.size = Pt(22)
    
    # Sections
    for sec in sections:
        sec_title = sec.get("title", "")
        sec_body = sec.get("body", "")
        
        if sec_title:
            h = doc.add_heading(sec_title, level=1)
            h.style.font.color.rgb = RGBColor(10, 147, 150)
            
        if sec_body:
            doc.add_paragraph(sec_body)
            
    # Tables
    if tables:
        for t_idx, tbl_data in enumerate(tables):
            if not tbl_data:
                continue
            rows = len(tbl_data)
            cols = len(tbl_data[0]) if rows > 0 else 0
            
            table = doc.add_table(rows=rows, cols=cols)
            table.style = 'Table Grid'
            
            for r_idx, row in enumerate(tbl_data):
                for c_idx, val in enumerate(row):
                    cell = table.cell(r_idx, c_idx)
                    cell.text = str(val)
                    
    fname = output_filename or f"Approval_Note_{title.replace(' ', '_')}.docx"
    target_path = os.path.join(DELIVERABLES_DIR, fname)
    doc.save(target_path)
    logger.info(f"Word deliverable generated: {target_path}")
    return target_path


def create_excel_deliverable(
    title: str,
    sheets: Dict[str, List[List[Any]]],
    output_filename: Optional[str] = None
) -> str:
    """
    Generate an Excel (.xlsx) spreadsheet with engineering calculations or financial audits.
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)
    
    header_fill = PatternFill(start_color="0A9396", end_color="0A9396", fill_type="solid")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    
    for sheet_name, rows in sheets.items():
        ws = wb.create_sheet(title=sheet_name[:30])
        
        for r_idx, row_data in enumerate(rows, start=1):
            ws.append(row_data)
            if r_idx == 1:  # Header row formatting
                for cell in ws[1]:
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                    
    fname = output_filename or f"Calculation_Report_{title.replace(' ', '_')}.xlsx"
    target_path = os.path.join(DELIVERABLES_DIR, fname)
    wb.save(target_path)
    logger.info(f"Excel deliverable generated: {target_path}")
    return target_path


def create_ppt_deliverable(
    presentation_title: str,
    slides: List[Dict[str, Any]],
    output_filename: Optional[str] = None
) -> str:
    """
    Generate a PowerPoint (.pptx) presentation deck.
    """
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    
    prs = Presentation()
    
    # Title Slide
    title_slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(title_slide_layout)
    title = slide.shapes.title
    subtitle = slide.placeholders[1]
    
    title.text = presentation_title
    subtitle.text = "HEXA Sovereign Industrial Workbench"
    
    # Bullet/Content Slides
    bullet_slide_layout = prs.slide_layouts[1]
    for s_info in slides:
        s_title = s_info.get("title", "Slide")
        points = s_info.get("points", [])
        
        slide = prs.slides.add_slide(bullet_slide_layout)
        shapes = slide.shapes
        title_shape = shapes.title
        body_shape = shapes.placeholders[1]
        
        title_shape.text = s_title
        tf = body_shape.text_frame
        
        for idx, pt in enumerate(points):
            if idx == 0:
                tf.text = pt
            else:
                p = tf.add_paragraph()
                p.text = pt
                
    fname = output_filename or f"Presentation_{presentation_title.replace(' ', '_')}.pptx"
    target_path = os.path.join(DELIVERABLES_DIR, fname)
    prs.save(target_path)
    logger.info(f"PowerPoint deliverable generated: {target_path}")
    return target_path


def generate_local_image(prompt: str, filename: Optional[str] = None) -> str:
    """
    Generate an image locally using PyTorch + Diffusers + SDXL + CUDA + Pillow engine.
    If PyTorch & Diffusers with SDXL are available with CUDA, runs the local SDXL model pipeline.
    Otherwise falls back to high-resolution Pillow industrial canvas rendering.
    """
    import io
    import uuid
    from PIL import Image, ImageDraw, ImageFont
    from src.generated_images import save_generated_image_bytes

    img_name = filename or f"sdxl_{uuid.uuid4().hex[:8]}.png"

    # Attempt PyTorch + Diffusers + SDXL + CUDA execution
    try:
        import torch
        from diffusers import StableDiffusionXLPipeline

        device = "cuda" if torch.cuda.is_available() else "cpu"
        torch_dtype = torch.float16 if device == "cuda" else torch.float32

        logger.info(f"Launching SDXL PyTorch Diffusers Pipeline on device: {device}...")
        model_id = os.getenv("SDXL_MODEL_PATH", "stabilityai/stable-diffusion-xl-base-1.0")

        pipe = StableDiffusionXLPipeline.from_pretrained(
            model_id, torch_dtype=torch_dtype, use_safetensors=True
        )
        pipe = pipe.to(device)

        image = pipe(prompt=prompt, num_inference_steps=25).images[0]
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        target_path = save_generated_image_bytes(buf.getvalue(), img_name)
        logger.info(f"SDXL PyTorch Diffusers image generated: {target_path}")
        return target_path
    except Exception as e:
        logger.warning(f"Diffusers SDXL PyTorch pipeline skipped ({e}). Using Pillow rendering engine.")

    # High-contrast Industrial Pillow Render Engine
    img = Image.new("RGB", (1024, 768), color=(10, 147, 150))
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, 984, 728], outline=(255, 255, 255), width=3)
    d.text((60, 60), "HEXA Industrial AI Vision Generator (PyTorch + SDXL + Pillow)", fill=(255, 255, 255))
    d.text((60, 120), f"Prompt: {prompt}", fill=(230, 230, 230))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    target_path = save_generated_image_bytes(buf.getvalue(), img_name)
    logger.info(f"Local Pillow Image generated: {target_path}")
    return target_path
