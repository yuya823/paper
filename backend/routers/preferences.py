"""User preferences API routes with authentication."""
from fastapi import APIRouter, Depends
from database import get_db
from auth import get_current_user
from models.schemas import UserPreferencesResponse, UserPreferencesUpdate

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


@router.get("/", response_model=UserPreferencesResponse)
async def get_preferences(user_id: str = Depends(get_current_user)):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM user_preferences WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if not row:
            # Create default preferences
            await db.execute(
                "INSERT INTO user_preferences (user_id) VALUES (?)", (user_id,)
            )
            await db.commit()
            return UserPreferencesResponse()

        return UserPreferencesResponse(
            sync_scroll=bool(row["sync_scroll"]),
            sync_zoom=bool(row["sync_zoom"]),
            show_highlight_link=bool(row["show_highlight_link"]),
            font_size_ja=row["font_size_ja"],
            font_family_ja=row["font_family_ja"],
            layout_mode=row["layout_mode"],
            translate_references=bool(row["translate_references"]),
            translate_captions=bool(row["translate_captions"]),
            translate_formulas=bool(row["translate_formulas"]),
            view_mode=row["view_mode"],
        )
    finally:
        await db.close()


@router.put("/", response_model=UserPreferencesResponse)
async def update_preferences(
    prefs: UserPreferencesUpdate,
    user_id: str = Depends(get_current_user),
):
    db = await get_db()
    try:
        # Ensure preferences row exists
        cursor = await db.execute(
            "SELECT id FROM user_preferences WHERE user_id = ?", (user_id,)
        )
        if not await cursor.fetchone():
            await db.execute(
                "INSERT INTO user_preferences (user_id) VALUES (?)", (user_id,)
            )

        updates = prefs.model_dump(exclude_none=True)
        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
            values = list(updates.values()) + [user_id]
            await db.execute(
                f"UPDATE user_preferences SET {set_clause} WHERE user_id = ?",
                values,
            )
            await db.commit()

        return await get_preferences(user_id)
    finally:
        await db.close()
