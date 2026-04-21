"""Database connection - supports both SQLite (local) and Supabase PostgreSQL."""
import aiosqlite
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY, LOCAL_DEV
from pathlib import Path

DATABASE_PATH = Path(__file__).parent / "paper_viewer.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001',
    original_filename TEXT NOT NULL,
    original_file_path TEXT,
    storage_path TEXT,
    title TEXT,
    authors TEXT,
    total_pages INTEGER,
    status TEXT DEFAULT 'uploaded',
    source_lang TEXT DEFAULT 'en',
    target_lang TEXT DEFAULT 'ja',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS page_blocks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    page_number INTEGER NOT NULL,
    block_index INTEGER NOT NULL,
    bbox_x0 REAL, bbox_y0 REAL, bbox_x1 REAL, bbox_y1 REAL,
    source_text TEXT,
    translated_text TEXT,
    block_type TEXT DEFAULT 'body',
    reading_order INTEGER,
    font_size REAL,
    font_name TEXT,
    is_translated INTEGER DEFAULT 0,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT UNIQUE NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001',
    sync_scroll INTEGER DEFAULT 1,
    sync_zoom INTEGER DEFAULT 1,
    show_highlight_link INTEGER DEFAULT 1,
    font_size_ja REAL DEFAULT 10.0,
    font_family_ja TEXT DEFAULT 'Noto Sans JP',
    layout_mode TEXT DEFAULT 'layout_priority',
    translate_references INTEGER DEFAULT 0,
    translate_captions INTEGER DEFAULT 1,
    translate_formulas INTEGER DEFAULT 0,
    view_mode TEXT DEFAULT 'single'
);

CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_page_blocks_document ON page_blocks(document_id);
CREATE INDEX IF NOT EXISTS idx_page_blocks_page ON page_blocks(document_id, page_number);
"""


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(str(DATABASE_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    db = await get_db()
    try:
        await db.executescript(SCHEMA_SQL)
        await db.commit()
    finally:
        await db.close()
