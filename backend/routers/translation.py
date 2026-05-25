"""Translation processing API routes with authentication."""
import os
import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from database import get_db, checkpoint_db
from auth import get_current_user
from services.pdf_parser import extract_all_pages
from services.translator import create_translator
from config import TRANSLATION_MODE, DEEPL_API_KEY, LOCAL_DEV
from models.schemas import TranslationRequest, PageBlockResponse, ProgressResponse

router = APIRouter(prefix="/api/translation", tags=["translation"])

# In-memory progress tracking
_progress: dict[str, ProgressResponse] = {}


# ── Background translation (SQLite - local dev) ─────

async def _run_translation_sqlite(doc_id: str, options: TranslationRequest):
    """Background task for local dev with SQLite."""
    print(f"[Translation] Starting (SQLite) for doc_id={doc_id}")
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        doc = await cursor.fetchone()
        if not doc:
            return

        file_path = doc["original_file_path"]
        _progress[doc_id] = ProgressResponse(
            document_id=doc_id, status="analyzing",
            progress=0.0, current_step="PDF解析中",
            message="テキストブロックを抽出しています..."
        )
        await db.execute("UPDATE documents SET status = 'analyzing' WHERE id = ?", (doc_id,))
        await db.commit()

        all_pages = extract_all_pages(file_path)
        total_blocks = sum(len(page) for page in all_pages)

        for page_blocks in all_pages:
            for block in page_blocks:
                await db.execute(
                    """INSERT OR REPLACE INTO page_blocks
                       (id, document_id, page_number, block_index, bbox_x0, bbox_y0, bbox_x1, bbox_y1,
                        source_text, block_type, reading_order, font_size, font_name)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (block["id"], doc_id, block["page_number"], block["block_index"],
                     block["bbox"]["x0"], block["bbox"]["y0"], block["bbox"]["x1"], block["bbox"]["y1"],
                     block["source_text"], block["block_type"],
                     block["reading_order"], block["font_size"], block["font_name"]),
                )
        await db.commit()
        await checkpoint_db(db)

        _progress[doc_id] = ProgressResponse(
            document_id=doc_id, status="translating", progress=0.1,
            current_step="翻訳中", message="テキストを翻訳しています..."
        )
        await db.execute("UPDATE documents SET status = 'translating' WHERE id = ?", (doc_id,))
        await db.commit()

        translator = create_translator(TRANSLATION_MODE, DEEPL_API_KEY)
        translated_count = 0
        for page_blocks in all_pages:
            for block in page_blocks:
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
                        print(f"Translation error for block {block['id']}: {e}")
                        await db.execute(
                            "UPDATE page_blocks SET translated_text = ? WHERE id = ?",
                            (f"[翻訳エラー] {block['source_text']}", block["id"]),
                        )
                translated_count += 1
                _progress[doc_id] = ProgressResponse(
                    document_id=doc_id, status="translating",
                    progress=0.1 + 0.85 * (translated_count / max(total_blocks, 1)),
                    current_step="翻訳中", message=f"{translated_count}/{total_blocks} ブロック完了"
                )

        await db.commit()
        await checkpoint_db(db)
        _progress[doc_id] = ProgressResponse(
            document_id=doc_id, status="completed", progress=1.0,
            current_step="完了", message="翻訳が完了しました"
        )
        await db.execute(
            "UPDATE documents SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (doc_id,),
        )
        await db.commit()
        await checkpoint_db(db)
        print(f"[Translation] Completed (SQLite) for doc_id={doc_id}")

    except Exception as e:
        _progress[doc_id] = ProgressResponse(
            document_id=doc_id, status="error", progress=0.0,
            current_step="エラー", message=str(e)
        )
        await db.execute("UPDATE documents SET status = 'error' WHERE id = ?", (doc_id,))
        await db.commit()
        print(f"[Translation] ERROR (SQLite) for doc_id={doc_id}: {e}")
    finally:
        await db.close()


# ── Background translation (Supabase - production) ──

async def _run_translation_supabase(doc_id: str, options: TranslationRequest):
    """Background task for production with Supabase."""
    import supabase_db as sb
    print(f"[Translation] Starting (Supabase) for doc_id={doc_id}")
    temp_path = None
    try:
        doc = sb.get_document_by_id(doc_id)
        if not doc:
            return

        _progress[doc_id] = ProgressResponse(
            document_id=doc_id, status="analyzing", progress=0.0,
            current_step="PDF解析中", message="テキストブロックを抽出しています..."
        )
        sb.update_document_status(doc_id, "analyzing")

        # Download PDF from Storage
        temp_path = sb.download_pdf_to_temp(doc["storage_path"])
        all_pages = extract_all_pages(temp_path)
        total_blocks = sum(len(page) for page in all_pages)

        # Save blocks to Supabase
        block_records = []
        for page_blocks in all_pages:
            for block in page_blocks:
                block_records.append({
                    "id": block["id"], "document_id": doc_id,
                    "page_number": block["page_number"], "block_index": block["block_index"],
                    "bbox_x0": block["bbox"]["x0"], "bbox_y0": block["bbox"]["y0"],
                    "bbox_x1": block["bbox"]["x1"], "bbox_y1": block["bbox"]["y1"],
                    "source_text": block["source_text"], "block_type": block["block_type"],
                    "reading_order": block["reading_order"],
                    "font_size": block["font_size"], "font_name": block["font_name"],
                })
        sb.insert_blocks(block_records)
        print(f"[Translation] Saved {total_blocks} blocks for doc_id={doc_id}")

        # Translate
        _progress[doc_id] = ProgressResponse(
            document_id=doc_id, status="translating", progress=0.1,
            current_step="翻訳中", message="テキストを翻訳しています..."
        )
        sb.update_document_status(doc_id, "translating")

        translator = create_translator(TRANSLATION_MODE, DEEPL_API_KEY)
        translated_count = 0
        for page_blocks in all_pages:
            for block in page_blocks:
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
                        sb.update_block_translation(block["id"], translated)
                    except Exception as e:
                        print(f"Translation error for block {block['id']}: {e}")
                        sb.update_block_translation(
                            block["id"],
                            f"[翻訳エラー] {block['source_text']}",
                            is_translated=False,
                        )

                translated_count += 1
                _progress[doc_id] = ProgressResponse(
                    document_id=doc_id, status="translating",
                    progress=0.1 + 0.85 * (translated_count / max(total_blocks, 1)),
                    current_step="翻訳中", message=f"{translated_count}/{total_blocks} ブロック完了"
                )

        _progress[doc_id] = ProgressResponse(
            document_id=doc_id, status="completed", progress=1.0,
            current_step="完了", message="翻訳が完了しました"
        )
        sb.update_document_status(doc_id, "completed")
        print(f"[Translation] Completed (Supabase) for doc_id={doc_id}")

    except Exception as e:
        _progress[doc_id] = ProgressResponse(
            document_id=doc_id, status="error", progress=0.0,
            current_step="エラー", message=str(e)
        )
        try:
            sb.update_document_status(doc_id, "error")
        except Exception:
            pass
        print(f"[Translation] ERROR (Supabase) for doc_id={doc_id}: {e}")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


# ── API Endpoints ────────────────────────────────────

@router.post("/{doc_id}/start")
async def start_translation(
    doc_id: str,
    background_tasks: BackgroundTasks,
    options: TranslationRequest = TranslationRequest(),
    user_id: str = Depends(get_current_user),
):
    """Start translation for a document. Supports re-translation."""
    if LOCAL_DEV:
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id))
            doc = await cursor.fetchone()
            if not doc:
                raise HTTPException(status_code=404, detail="ドキュメントが見つかりません")
            if doc["status"] in ("analyzing", "translating"):
                raise HTTPException(status_code=400, detail="すでに処理中です")
            if doc["status"] in ("completed", "error"):
                await db.execute("DELETE FROM page_blocks WHERE document_id = ?", (doc_id,))
                await db.execute("UPDATE documents SET status = 'uploaded' WHERE id = ?", (doc_id,))
                await db.commit()
            background_tasks.add_task(_run_translation_sqlite, doc_id, options)
            return {"message": "翻訳を開始しました", "document_id": doc_id}
        finally:
            await db.close()
    else:
        import supabase_db as sb
        doc = sb.get_document(doc_id, user_id)
        if not doc:
            raise HTTPException(status_code=404, detail="ドキュメントが見つかりません")
        if doc["status"] in ("analyzing", "translating"):
            raise HTTPException(status_code=400, detail="すでに処理中です")
        if doc["status"] in ("completed", "error"):
            sb.delete_blocks(doc_id)
            sb.update_document_status(doc_id, "uploaded")
        background_tasks.add_task(_run_translation_supabase, doc_id, options)
        return {"message": "翻訳を開始しました", "document_id": doc_id}


@router.get("/{doc_id}/progress", response_model=ProgressResponse)
async def get_progress(doc_id: str, user_id: str = Depends(get_current_user)):
    """Get translation progress."""
    if doc_id in _progress:
        return _progress[doc_id]

    if LOCAL_DEV:
        db = await get_db()
        try:
            cursor = await db.execute("SELECT status FROM documents WHERE id = ?", (doc_id,))
            doc = await cursor.fetchone()
            if not doc:
                raise HTTPException(status_code=404, detail="ドキュメントが見つかりません")
            return ProgressResponse(
                document_id=doc_id, status=doc["status"],
                progress=1.0 if doc["status"] == "completed" else 0.0,
                current_step=doc["status"],
            )
        finally:
            await db.close()
    else:
        import supabase_db as sb
        doc = sb.get_document_by_id(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="ドキュメントが見つかりません")
        return ProgressResponse(
            document_id=doc_id, status=doc["status"],
            progress=1.0 if doc["status"] == "completed" else 0.0,
            current_step=doc["status"],
        )


@router.get("/{doc_id}/blocks")
async def get_blocks(doc_id: str, page: int = None, user_id: str = Depends(get_current_user)):
    """Get translated blocks for a document."""
    if LOCAL_DEV:
        db = await get_db()
        try:
            if page is not None:
                cursor = await db.execute(
                    "SELECT * FROM page_blocks WHERE document_id = ? AND page_number = ? ORDER BY reading_order",
                    (doc_id, page),
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM page_blocks WHERE document_id = ? ORDER BY page_number, reading_order",
                    (doc_id,),
                )
            rows = await cursor.fetchall()
            return [_row_to_block(row) for row in rows]
        finally:
            await db.close()
    else:
        import supabase_db as sb
        rows = sb.get_blocks(doc_id, page)
        return [_sb_row_to_block(r) for r in rows]


@router.post("/{doc_id}/search")
async def search_blocks(doc_id: str, query: str, search_in: str = "both", user_id: str = Depends(get_current_user)):
    """Search text in blocks."""
    if LOCAL_DEV:
        db = await get_db()
        try:
            results = []
            if search_in in ("source", "both"):
                cursor = await db.execute(
                    "SELECT * FROM page_blocks WHERE document_id = ? AND source_text LIKE ? ORDER BY page_number, reading_order",
                    (doc_id, f"%{query}%"),
                )
                rows = await cursor.fetchall()
                for row in rows:
                    text = row["source_text"]
                    idx = text.lower().find(query.lower())
                    s, e = max(0, idx - 30), min(len(text), idx + len(query) + 30)
                    snippet = ("..." if s > 0 else "") + text[s:e] + ("..." if e < len(text) else "")
                    results.append({"block_id": row["id"], "page_number": row["page_number"],
                                    "block_index": row["block_index"], "text": text,
                                    "field": "source", "snippet": snippet})
            if search_in in ("translated", "both"):
                cursor = await db.execute(
                    "SELECT * FROM page_blocks WHERE document_id = ? AND translated_text LIKE ? ORDER BY page_number, reading_order",
                    (doc_id, f"%{query}%"),
                )
                rows = await cursor.fetchall()
                for row in rows:
                    text = row["translated_text"] or ""
                    idx = text.lower().find(query.lower())
                    if idx < 0:
                        continue
                    s, e = max(0, idx - 30), min(len(text), idx + len(query) + 30)
                    snippet = ("..." if s > 0 else "") + text[s:e] + ("..." if e < len(text) else "")
                    results.append({"block_id": row["id"], "page_number": row["page_number"],
                                    "block_index": row["block_index"], "text": text,
                                    "field": "translated", "snippet": snippet})
            return {"results": results, "total": len(results)}
        finally:
            await db.close()
    else:
        import supabase_db as sb
        results = sb.search_blocks(doc_id, query, search_in)
        return {"results": results, "total": len(results)}


# ── Helpers ──

def _row_to_block(row) -> dict:
    return {
        "id": row["id"], "document_id": row["document_id"],
        "page_number": row["page_number"], "block_index": row["block_index"],
        "bbox": {"x0": row["bbox_x0"], "y0": row["bbox_y0"],
                 "x1": row["bbox_x1"], "y1": row["bbox_y1"]},
        "source_text": row["source_text"], "translated_text": row["translated_text"],
        "block_type": row["block_type"], "reading_order": row["reading_order"],
        "font_size": row["font_size"], "font_name": row["font_name"],
        "is_translated": bool(row["is_translated"]),
    }


def _sb_row_to_block(r: dict) -> dict:
    return {
        "id": r["id"], "document_id": r["document_id"],
        "page_number": r["page_number"], "block_index": r["block_index"],
        "bbox": {"x0": r["bbox_x0"], "y0": r["bbox_y0"],
                 "x1": r["bbox_x1"], "y1": r["bbox_y1"]},
        "source_text": r.get("source_text"), "translated_text": r.get("translated_text"),
        "block_type": r.get("block_type", "body"), "reading_order": r.get("reading_order"),
        "font_size": r.get("font_size"), "font_name": r.get("font_name"),
        "is_translated": bool(r.get("is_translated")),
    }
