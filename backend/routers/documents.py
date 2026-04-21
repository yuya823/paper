"""Document management API routes with authentication."""
import uuid
import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse
from database import get_db
from auth import get_current_user
from config import UPLOAD_DIR, MAX_UPLOAD_SIZE_BYTES
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


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(user_id: str = Depends(get_current_user)):
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


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: str, user_id: str = Depends(get_current_user)):
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


@router.delete("/{doc_id}")
async def delete_document(doc_id: str, user_id: str = Depends(get_current_user)):
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


@router.get("/{doc_id}/pdf")
async def get_pdf_file(doc_id: str, user_id: str = Depends(get_current_user)):
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


@router.get("/{doc_id}/dimensions")
async def get_dimensions(doc_id: str, user_id: str = Depends(get_current_user)):
    from services.pdf_parser import get_page_dimensions
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
