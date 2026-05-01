"""Translation processing API routes with authentication."""
import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from database import get_db
from auth import get_current_user
from services.pdf_parser import extract_all_pages
from services.translator import create_translator
from config import TRANSLATION_MODE, DEEPL_API_KEY
from models.schemas import TranslationRequest, PageBlockResponse, ProgressResponse

router = APIRouter(prefix="/api/translation", tags=["translation"])

# In-memory progress tracking
_progress: dict[str, ProgressResponse] = {}


async def _run_translation(doc_id: str, options: TranslationRequest):
    """Background task: extract blocks and translate them."""
    db = await get_db()
    try:
        # Get document
        cursor = await db.execute(
            "SELECT * FROM documents WHERE id = ?", (doc_id,)
        )
        doc = await cursor.fetchone()
        if not doc:
            return

        file_path = doc["original_file_path"]

        # Update status
        _progress[doc_id] = ProgressResponse(
            document_id=doc_id, status="analyzing",
            progress=0.0, current_step="PDF解析中",
            message="テキストブロックを抽出しています..."
        )
        await db.execute(
            "UPDATE documents SET status = 'analyzing' WHERE id = ?", (doc_id,)
        )
        await db.commit()

        # Extract all pages
        all_pages = extract_all_pages(file_path)
        total_blocks = sum(len(page) for page in all_pages)

        # Save blocks to database
        for page_blocks in all_pages:
            for block in page_blocks:
                await db.execute(
                    """INSERT OR REPLACE INTO page_blocks
                       (id, document_id, page_number, block_index, bbox_x0, bbox_y0, bbox_x1, bbox_y1,
                        source_text, block_type, reading_order, font_size, font_name)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        block["id"], doc_id, block["page_number"], block["block_index"],
                        block["bbox"]["x0"], block["bbox"]["y0"],
                        block["bbox"]["x1"], block["bbox"]["y1"],
                        block["source_text"], block["block_type"],
                        block["reading_order"], block["font_size"], block["font_name"],
                    ),
                )
        await db.commit()

        # Start translation
        _progress[doc_id] = ProgressResponse(
            document_id=doc_id, status="translating",
            progress=0.1, current_step="翻訳中",
            message="テキストを翻訳しています..."
        )
        await db.execute(
            "UPDATE documents SET status = 'translating' WHERE id = ?", (doc_id,)
        )
        await db.commit()

        translator = create_translator(TRANSLATION_MODE, DEEPL_API_KEY)

        translated_count = 0
        for page_blocks in all_pages:
            for block in page_blocks:
                # Skip non-translatable blocks
                should_translate = True
                if block["block_type"] == "formula" and not options.translate_formulas:
                    should_translate = False
                elif block["block_type"] == "reference" and not options.translate_references:
                    should_translate = False
                elif block["block_type"] == "footer":
                    should_translate = False

                if should_translate and block["source_text"].strip():
                    try:
                        translated = await translator.translate(block["source_text"])
                        await db.execute(
                            "UPDATE page_blocks SET translated_text = ?, is_translated = 1 WHERE id = ?",
                            (translated, block["id"]),
                        )
                    except Exception as e:
                        error_type = type(e).__name__
                        print(f"Translation error for block {block['id']} ({error_type}): {e}")
                        # Save original text as fallback so user can still read the content
                        await db.execute(
                            "UPDATE page_blocks SET translated_text = ? WHERE id = ?",
                            (f"[翻訳エラー: {error_type}] {block['source_text']}", block["id"]),
                        )

                translated_count += 1
                progress = 0.1 + 0.85 * (translated_count / max(total_blocks, 1))
                _progress[doc_id] = ProgressResponse(
                    document_id=doc_id, status="translating",
                    progress=progress, current_step="翻訳中",
                    message=f"{translated_count}/{total_blocks} ブロック完了"
                )

        await db.commit()

        # Complete
        _progress[doc_id] = ProgressResponse(
            document_id=doc_id, status="completed",
            progress=1.0, current_step="完了",
            message="翻訳が完了しました"
        )
        await db.execute(
            "UPDATE documents SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (doc_id,),
        )
        await db.commit()

    except Exception as e:
        _progress[doc_id] = ProgressResponse(
            document_id=doc_id, status="error",
            progress=0.0, current_step="エラー",
            message=str(e)
        )
        await db.execute(
            "UPDATE documents SET status = 'error' WHERE id = ?", (doc_id,)
        )
        await db.commit()
    finally:
        await db.close()


@router.post("/{doc_id}/start")
async def start_translation(
    doc_id: str,
    background_tasks: BackgroundTasks,
    options: TranslationRequest = TranslationRequest(),
    user_id: str = Depends(get_current_user),
):
    """Start translation for a document. Supports re-translation."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id))
        doc = await cursor.fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="ドキュメントが見つかりません")

        if doc["status"] in ("analyzing", "translating"):
            raise HTTPException(status_code=400, detail="すでに処理中です")

        # For re-translation: delete old blocks
        if doc["status"] in ("completed", "error"):
            await db.execute("DELETE FROM page_blocks WHERE document_id = ?", (doc_id,))
            await db.execute(
                "UPDATE documents SET status = 'uploaded' WHERE id = ?", (doc_id,)
            )
            await db.commit()

        background_tasks.add_task(_run_translation, doc_id, options)

        return {"message": "翻訳を開始しました", "document_id": doc_id}
    finally:
        await db.close()


@router.get("/{doc_id}/progress", response_model=ProgressResponse)
async def get_progress(doc_id: str, user_id: str = Depends(get_current_user)):
    """Get translation progress."""
    if doc_id in _progress:
        return _progress[doc_id]

    # Check DB status
    db = await get_db()
    try:
        cursor = await db.execute("SELECT status FROM documents WHERE id = ?", (doc_id,))
        doc = await cursor.fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="ドキュメントが見つかりません")

        return ProgressResponse(
            document_id=doc_id,
            status=doc["status"],
            progress=1.0 if doc["status"] == "completed" else 0.0,
            current_step=doc["status"],
        )
    finally:
        await db.close()


@router.get("/{doc_id}/blocks")
async def get_blocks(doc_id: str, page: int = None, user_id: str = Depends(get_current_user)):
    """Get translated blocks for a document, optionally filtered by page."""
    db = await get_db()
    try:
        if page is not None:
            cursor = await db.execute(
                """SELECT * FROM page_blocks WHERE document_id = ? AND page_number = ?
                   ORDER BY reading_order""",
                (doc_id, page),
            )
        else:
            cursor = await db.execute(
                """SELECT * FROM page_blocks WHERE document_id = ?
                   ORDER BY page_number, reading_order""",
                (doc_id,),
            )

        rows = await cursor.fetchall()
        return [
            {
                "id": row["id"],
                "document_id": row["document_id"],
                "page_number": row["page_number"],
                "block_index": row["block_index"],
                "bbox": {
                    "x0": row["bbox_x0"],
                    "y0": row["bbox_y0"],
                    "x1": row["bbox_x1"],
                    "y1": row["bbox_y1"],
                },
                "source_text": row["source_text"],
                "translated_text": row["translated_text"],
                "block_type": row["block_type"],
                "reading_order": row["reading_order"],
                "font_size": row["font_size"],
                "font_name": row["font_name"],
                "is_translated": bool(row["is_translated"]),
            }
            for row in rows
        ]
    finally:
        await db.close()


@router.post("/{doc_id}/search")
async def search_blocks(doc_id: str, query: str, search_in: str = "both", user_id: str = Depends(get_current_user)):
    """Search text in blocks."""
    db = await get_db()
    try:
        results = []

        if search_in in ("source", "both"):
            cursor = await db.execute(
                """SELECT * FROM page_blocks
                   WHERE document_id = ? AND source_text LIKE ?
                   ORDER BY page_number, reading_order""",
                (doc_id, f"%{query}%"),
            )
            rows = await cursor.fetchall()
            for row in rows:
                text = row["source_text"]
                idx = text.lower().find(query.lower())
                start = max(0, idx - 30)
                end = min(len(text), idx + len(query) + 30)
                snippet = ("..." if start > 0 else "") + text[start:end] + ("..." if end < len(text) else "")

                results.append({
                    "block_id": row["id"],
                    "page_number": row["page_number"],
                    "block_index": row["block_index"],
                    "text": text,
                    "field": "source",
                    "snippet": snippet,
                })

        if search_in in ("translated", "both"):
            cursor = await db.execute(
                """SELECT * FROM page_blocks
                   WHERE document_id = ? AND translated_text LIKE ?
                   ORDER BY page_number, reading_order""",
                (doc_id, f"%{query}%"),
            )
            rows = await cursor.fetchall()
            for row in rows:
                text = row["translated_text"] or ""
                idx = text.lower().find(query.lower())
                if idx < 0:
                    continue
                start = max(0, idx - 30)
                end = min(len(text), idx + len(query) + 30)
                snippet = ("..." if start > 0 else "") + text[start:end] + ("..." if end < len(text) else "")

                results.append({
                    "block_id": row["id"],
                    "page_number": row["page_number"],
                    "block_index": row["block_index"],
                    "text": text,
                    "field": "translated",
                    "snippet": snippet,
                })

        return {"results": results, "total": len(results)}
    finally:
        await db.close()
