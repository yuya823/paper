"""Supabase database and storage operations for production."""
import os
import tempfile
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


# ── Documents ────────────────────────────────────────

def insert_document(doc_id: str, user_id: str, filename: str,
                    storage_path: str, title: str, authors: str,
                    total_pages: int) -> dict:
    sb = get_client()
    result = sb.table("documents").insert({
        "id": doc_id, "user_id": user_id,
        "original_filename": filename, "storage_path": storage_path,
        "title": title, "authors": authors,
        "total_pages": total_pages, "status": "uploaded",
    }).execute()
    return result.data[0] if result.data else {}


def get_document(doc_id: str, user_id: str) -> dict | None:
    sb = get_client()
    result = (sb.table("documents").select("*")
              .eq("id", doc_id).eq("user_id", user_id).execute())
    return result.data[0] if result.data else None


def get_document_by_id(doc_id: str) -> dict | None:
    """Get document without user filter (for background tasks)."""
    sb = get_client()
    result = sb.table("documents").select("*").eq("id", doc_id).execute()
    return result.data[0] if result.data else None


def list_documents(user_id: str) -> list[dict]:
    sb = get_client()
    result = (sb.table("documents").select("*")
              .eq("user_id", user_id)
              .order("created_at", desc=True).execute())
    return result.data


def update_document_status(doc_id: str, status: str):
    sb = get_client()
    sb.table("documents").update({"status": status}).eq("id", doc_id).execute()


def delete_document(doc_id: str, user_id: str) -> bool:
    sb = get_client()
    doc = get_document(doc_id, user_id)
    if not doc:
        return False
    sb.table("page_blocks").delete().eq("document_id", doc_id).execute()
    sb.table("documents").delete().eq("id", doc_id).execute()
    if doc.get("storage_path"):
        try:
            sb.storage.from_("papers").remove([doc["storage_path"]])
        except Exception:
            pass
    return True


# ── Page Blocks ──────────────────────────────────────

def insert_blocks(blocks: list[dict]):
    """Batch insert page blocks."""
    if not blocks:
        return
    sb = get_client()
    for i in range(0, len(blocks), 50):
        batch = blocks[i:i + 50]
        sb.table("page_blocks").insert(batch).execute()


def update_block_translation(block_id: str, translated_text: str,
                             is_translated: bool = True):
    sb = get_client()
    sb.table("page_blocks").update({
        "translated_text": translated_text,
        "is_translated": is_translated,
    }).eq("id", block_id).execute()


def get_blocks(doc_id: str, page: int | None = None) -> list[dict]:
    sb = get_client()
    query = sb.table("page_blocks").select("*").eq("document_id", doc_id)
    if page is not None:
        query = query.eq("page_number", page)
    result = query.order("page_number").order("reading_order").execute()
    return result.data


def delete_blocks(doc_id: str):
    sb = get_client()
    sb.table("page_blocks").delete().eq("document_id", doc_id).execute()


def search_blocks(doc_id: str, query_text: str,
                  search_in: str = "both") -> list[dict]:
    sb = get_client()
    results = []

    if search_in in ("source", "both"):
        res = (sb.table("page_blocks").select("*")
               .eq("document_id", doc_id)
               .ilike("source_text", f"%{query_text}%")
               .order("page_number").order("reading_order").execute())
        for row in res.data:
            text = row.get("source_text") or ""
            idx = text.lower().find(query_text.lower())
            if idx < 0:
                continue
            s, e = max(0, idx - 30), min(len(text), idx + len(query_text) + 30)
            snippet = ("..." if s > 0 else "") + text[s:e] + ("..." if e < len(text) else "")
            results.append({"block_id": row["id"], "page_number": row["page_number"],
                            "block_index": row["block_index"], "text": text,
                            "field": "source", "snippet": snippet})

    if search_in in ("translated", "both"):
        res = (sb.table("page_blocks").select("*")
               .eq("document_id", doc_id)
               .ilike("translated_text", f"%{query_text}%")
               .order("page_number").order("reading_order").execute())
        for row in res.data:
            text = row.get("translated_text") or ""
            idx = text.lower().find(query_text.lower())
            if idx < 0:
                continue
            s, e = max(0, idx - 30), min(len(text), idx + len(query_text) + 30)
            snippet = ("..." if s > 0 else "") + text[s:e] + ("..." if e < len(text) else "")
            results.append({"block_id": row["id"], "page_number": row["page_number"],
                            "block_index": row["block_index"], "text": text,
                            "field": "translated", "snippet": snippet})

    return results


# ── Preferences ──────────────────────────────────────

def get_preferences(user_id: str) -> dict | None:
    sb = get_client()
    result = (sb.table("user_preferences").select("*")
              .eq("user_id", user_id).execute())
    return result.data[0] if result.data else None


def upsert_preferences(user_id: str, prefs: dict) -> dict:
    sb = get_client()
    data = {"user_id": user_id, **prefs}
    result = (sb.table("user_preferences")
              .upsert(data, on_conflict="user_id").execute())
    return result.data[0] if result.data else {}


# ── Storage ──────────────────────────────────────────

def upload_pdf(storage_path: str, file_bytes: bytes):
    sb = get_client()
    sb.storage.from_("papers").upload(
        storage_path, file_bytes,
        {"content-type": "application/pdf"},
    )


def download_pdf(storage_path: str) -> bytes:
    sb = get_client()
    return sb.storage.from_("papers").download(storage_path)


def download_pdf_to_temp(storage_path: str) -> str:
    """Download PDF to a temp file and return the file path."""
    data = download_pdf(storage_path)
    fd, path = tempfile.mkstemp(suffix=".pdf")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return path
