"""Pydantic schemas for API request/response models."""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DocumentResponse(BaseModel):
    id: str
    original_filename: str
    title: Optional[str] = None
    authors: Optional[str] = None
    total_pages: Optional[int] = None
    status: str
    source_lang: str = "en"
    target_lang: str = "ja"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PageBlockResponse(BaseModel):
    id: str
    document_id: str
    page_number: int
    block_index: int
    bbox: dict  # {x0, y0, x1, y1}
    source_text: str
    translated_text: Optional[str] = None
    block_type: str = "body"
    reading_order: Optional[int] = None
    font_size: Optional[float] = None
    font_name: Optional[str] = None
    is_translated: bool = False


class TranslationRequest(BaseModel):
    translate_references: bool = False
    translate_captions: bool = True
    translate_formulas: bool = False


class UserPreferencesResponse(BaseModel):
    sync_scroll: bool = True
    sync_zoom: bool = True
    show_highlight_link: bool = True
    font_size_ja: float = 10.0
    font_family_ja: str = "Noto Sans JP"
    layout_mode: str = "layout_priority"
    translate_references: bool = False
    translate_captions: bool = True
    translate_formulas: bool = False
    view_mode: str = "single"


class UserPreferencesUpdate(BaseModel):
    sync_scroll: Optional[bool] = None
    sync_zoom: Optional[bool] = None
    show_highlight_link: Optional[bool] = None
    font_size_ja: Optional[float] = None
    font_family_ja: Optional[str] = None
    layout_mode: Optional[str] = None
    translate_references: Optional[bool] = None
    translate_captions: Optional[bool] = None
    translate_formulas: Optional[bool] = None
    view_mode: Optional[str] = None


class ProgressResponse(BaseModel):
    document_id: str
    status: str
    progress: float = 0.0  # 0.0 - 1.0
    current_step: str = ""
    message: str = ""


class SearchRequest(BaseModel):
    query: str
    search_in: str = "both"  # "source", "translated", "both"
    document_id: str


class SearchResult(BaseModel):
    block_id: str
    page_number: int
    block_index: int
    text: str
    field: str  # "source" or "translated"
    snippet: str
