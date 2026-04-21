"""Authentication middleware for Supabase JWT verification."""
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from config import SUPABASE_JWT_SECRET, LOCAL_DEV

security = HTTPBearer(auto_error=False)

DEV_USER_ID = "00000000-0000-0000-0000-000000000001"


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Extract and verify user ID from Supabase JWT token.
    In LOCAL_DEV mode, returns a fixed dev user ID.
    """
    if LOCAL_DEV:
        return DEV_USER_ID

    if not credentials:
        raise HTTPException(status_code=401, detail="認証が必要です")

    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="無効なトークンです")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="トークンの検証に失敗しました")
