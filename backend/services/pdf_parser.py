"""PDF parsing service using PyMuPDF."""
import fitz
import uuid
import re
from typing import Optional
from pathlib import Path


def extract_document_info(pdf_path: str) -> dict:
    """Extract document metadata (title, authors, page count)."""
    doc = fitz.open(pdf_path)
    metadata = doc.metadata or {}

    title = metadata.get("title", "")
    author = metadata.get("author", "")

    # If no title in metadata, try first page first line
    if not title:
        first_page = doc[0]
        blocks = first_page.get_text("dict")["blocks"]
        for block in blocks:
            if block.get("type") == 0:  # text block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if len(text) > 5 and span.get("size", 0) > 12:
                            title = text
                            break
                    if title:
                        break
            if title:
                break

    total_pages = len(doc)
    doc.close()

    return {
        "title": title or "Untitled",
        "authors": author,
        "total_pages": total_pages,
    }


def extract_page_blocks(pdf_path: str, page_number: int) -> list[dict]:
    """Extract text blocks with coordinates from a specific page."""
    doc = fitz.open(pdf_path)
    page = doc[page_number]

    blocks_data = page.get_text("dict")["blocks"]
    page_width = page.rect.width
    page_height = page.rect.height

    result = []
    block_index = 0

    for block in blocks_data:
        if block.get("type") != 0:  # Skip image blocks
            continue

        bbox = block.get("bbox", (0, 0, 0, 0))
        lines = block.get("lines", [])

        # Combine all text in the block
        full_text = ""
        max_font_size = 0
        font_name = ""

        for line in lines:
            line_text = ""
            for span in line.get("spans", []):
                line_text += span.get("text", "")
                span_size = span.get("size", 0)
                if span_size > max_font_size:
                    max_font_size = span_size
                    font_name = span.get("font", "")
            full_text += line_text + "\n"

        full_text = full_text.strip()

        if not full_text or len(full_text) < 2:
            continue

        # Classify block type
        block_type = classify_block(
            full_text, max_font_size, bbox, page_width, page_height
        )

        result.append({
            "id": str(uuid.uuid4()),
            "page_number": page_number,
            "block_index": block_index,
            "bbox": {
                "x0": round(bbox[0], 2),
                "y0": round(bbox[1], 2),
                "x1": round(bbox[2], 2),
                "y1": round(bbox[3], 2),
            },
            "source_text": full_text,
            "translated_text": None,
            "block_type": block_type,
            "reading_order": block_index,
            "font_size": round(max_font_size, 2),
            "font_name": font_name,
            "page_width": round(page_width, 2),
            "page_height": round(page_height, 2),
        })
        block_index += 1

    doc.close()
    return result


def classify_block(
    text: str,
    font_size: float,
    bbox: tuple,
    page_width: float,
    page_height: float,
) -> str:
    """Classify a text block by its type."""
    text_lower = text.lower().strip()

    # Formula detection (contains many math symbols)
    math_chars = set("∑∏∫∂∇√∞±≤≥≈≠∈∉⊂⊃∪∩αβγδεζηθικλμνξπρστυφχψω")
    if len(set(text) & math_chars) > 2:
        return "formula"

    # Figure/Table caption
    if re.match(r'^(fig(ure)?|table|tab)\s*\.?\s*\d', text_lower):
        return "caption"

    # Heading detection (large font, short text)
    if font_size > 13 and len(text) < 200:
        return "heading"

    # Page header/footer (near top/bottom, small text)
    y_center = (bbox[1] + bbox[3]) / 2
    if y_center < page_height * 0.05 or y_center > page_height * 0.95:
        if len(text) < 100:
            return "footer"

    # References section detection
    if text_lower.startswith("references") or text_lower.startswith("bibliography"):
        return "heading"
    if re.match(r'^\[\d+\]', text_lower) or re.match(r'^\d+\.\s+[A-Z]', text):
        return "reference"

    return "body"


def extract_all_pages(pdf_path: str) -> list[list[dict]]:
    """Extract blocks from all pages."""
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    doc.close()

    all_pages = []
    for page_num in range(total_pages):
        blocks = extract_page_blocks(pdf_path, page_num)
        all_pages.append(blocks)

    return all_pages


def get_page_dimensions(pdf_path: str) -> list[dict]:
    """Get dimensions of each page."""
    doc = fitz.open(pdf_path)
    dims = []
    for page in doc:
        dims.append({
            "width": round(page.rect.width, 2),
            "height": round(page.rect.height, 2),
        })
    doc.close()
    return dims
