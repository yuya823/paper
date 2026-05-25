"""Document management API routes with authentication."""
import uuid
import os
import shutil
import tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse, Response
from database import get_db
from auth import get_current_user
from config import UPLOAD_DIR, MAX_UPLOAD_SIZE_BYTES, LOCAL_DEV
from services.pdf_parser import extract_document_info
from models.schemas import DocumentResponse

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDFファイルのみアップロード可能です")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="ファイルサイズが上限を超えています")

    doc_id = str(uuid.uuid4())

    if LOCAL_DEV:
        doc_dir = UPLOAD_DIR / user_id / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        file_path = doc_dir / file.filename
        with open(file_path, "wb") as f:
            f.write(content)
        try:
            info = extract_document_info(str(file_path))
        except Exception as e:
            shutil.rmtree(doc_dir)
            raise HTTPException(status_code=400, detail=f"PDF解析エラー: {str(e)}")
        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO documents (id, user_id, original_filename, original_file_path, title, authors, total_pages, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (doc_id, user_id, file.filename, str(file_path), info["title"], info["authors"], info["total_pages"], "uploaded"),
            )
            await db.commit()
            return DocumentResponse(
                id=doc_id, original_filename=file.filename,
                title=info["title"], authors=info["authors"],
                total_pages=info["total_pages"], status="uploaded",
            )
        finally:
            await db.close()
    else:
        import supabase_db as sb
        # Parse PDF from temp file
        fd, temp_path = tempfile.mkstemp(suffix=".pdf")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(content)
            info = extract_document_info(temp_path)
        except Exception as e:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise HTTPException(status_code=400, detail=f"PDF解析エラー: {str(e)}")
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

        storage_path = f"{user_id}/{doc_id}/{file.filename}"
        try:
            sb.upload_pdf(storage_path, content)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"ストレージエラー: {str(e)}")

        sb.insert_document(
            doc_id=doc_id, user_id=user_id, filename=file.filename,
            storage_path=storage_path, title=info["title"],
            authors=info["authors"], total_pages=info["total_pages"],
        )
        return DocumentResponse(
            id=doc_id, original_filename=file.filename,
            title=info["title"], authors=info["authors"],
            total_pages=info["total_pages"], status="uploaded",
        )


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(user_id: str = Depends(get_current_user)):
    if LOCAL_DEV:
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT * FROM documents WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
            )
            rows = await cursor.fetchall()
            return [
                DocumentResponse(
                    id=row["id"], original_filename=row["original_filename"],
                    title=row["title"], authors=row["authors"],
                    total_pages=row["total_pages"], status=row["status"],
                    source_lang=row["source_lang"], target_lang=row["target_lang"],
                    created_at=row["created_at"], updated_at=row["updated_at"],
                )
                for row in rows
            ]
        finally:
            await db.close()
    else:
        import supabase_db as sb
        rows = sb.list_documents(user_id)
        return [
            DocumentResponse(
                id=r["id"], original_filename=r["original_filename"],
                title=r.get("title"), authors=r.get("authors"),
                total_pages=r.get("total_pages"), status=r["status"],
                source_lang=r.get("source_lang", "en"), target_lang=r.get("target_lang", "ja"),
                created_at=str(r["created_at"]) if r.get("created_at") else None,
                updated_at=str(r["updated_at"]) if r.get("updated_at") else None,
            )
            for r in rows
        ]


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: str, user_id: str = Depends(get_current_user)):
    if LOCAL_DEV:
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT * FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id)
            )
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="ドキュメントが見つかりません")
            return DocumentResponse(
                id=row["id"], original_filename=row["original_filename"],
                title=row["title"], authors=row["authors"],
                total_pages=row["total_pages"], status=row["status"],
                source_lang=row["source_lang"], target_lang=row["target_lang"],
                created_at=row["created_at"], updated_at=row["updated_at"],
            )
        finally:
            await db.close()
    else:
        import supabase_db as sb
        r = sb.get_document(doc_id, user_id)
        if not r:
            raise HTTPException(status_code=404, detail="ドキュメントが見つかりません")
        return DocumentResponse(
            id=r["id"], original_filename=r["original_filename"],
            title=r.get("title"), authors=r.get("authors"),
            total_pages=r.get("total_pages"), status=r["status"],
            source_lang=r.get("source_lang", "en"), target_lang=r.get("target_lang", "ja"),
            created_at=str(r["created_at"]) if r.get("created_at") else None,
            updated_at=str(r["updated_at"]) if r.get("updated_at") else None,
        )


@router.delete("/{doc_id}")
async def delete_document(doc_id: str, user_id: str = Depends(get_current_user)):
    if LOCAL_DEV:
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT original_file_path FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id)
            )
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="ドキュメントが見つかりません")
            doc_dir = UPLOAD_DIR / user_id / doc_id
            if doc_dir.exists():
                shutil.rmtree(doc_dir)
            await db.execute("DELETE FROM page_blocks WHERE document_id = ?", (doc_id,))
            await db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            await db.commit()
            return {"message": "削除しました"}
        finally:
            await db.close()
    else:
        import supabase_db as sb
        if not sb.delete_document(doc_id, user_id):
            raise HTTPException(status_code=404, detail="ドキュメントが見つかりません")
        return {"message": "削除しました"}


@router.get("/{doc_id}/pdf")
async def get_pdf_file(doc_id: str, user_id: str = Depends(get_current_user)):
    if LOCAL_DEV:
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT original_file_path FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id)
            )
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="ドキュメントが見つかりません")
            file_path = row["original_file_path"]
            if not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail="PDFファイルが見つかりません")
            return FileResponse(file_path, media_type="application/pdf")
        finally:
            await db.close()
    else:
        import supabase_db as sb
        doc = sb.get_document(doc_id, user_id)
        if not doc or not doc.get("storage_path"):
            raise HTTPException(status_code=404, detail="ドキュメントが見つかりません")
        try:
            pdf_data = sb.download_pdf(doc["storage_path"])
            return Response(content=pdf_data, media_type="application/pdf")
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"PDFダウンロードエラー: {str(e)}")


@router.get("/{doc_id}/dimensions")
async def get_dimensions(doc_id: str, user_id: str = Depends(get_current_user)):
    from services.pdf_parser import get_page_dimensions

    if LOCAL_DEV:
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT original_file_path FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id)
            )
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="ドキュメントが見つかりません")
            dims = get_page_dimensions(row["original_file_path"])
            return {"dimensions": dims}
        finally:
            await db.close()
    else:
        import supabase_db as sb
        doc = sb.get_document(doc_id, user_id)
        if not doc or not doc.get("storage_path"):
            raise HTTPException(status_code=404, detail="ドキュメントが見つかりません")
        temp_path = sb.download_pdf_to_temp(doc["storage_path"])
        try:
            dims = get_page_dimensions(temp_path)
            return {"dimensions": dims}
        finally:
            os.unlink(temp_path)
