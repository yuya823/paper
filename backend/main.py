"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from config import FRONTEND_URL
from routers import documents, translation, preferences


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    await init_db()
    yield


app = FastAPI(
    title="Paper Translator API",
    description="英語論文PDF対訳ビューア バックエンドAPI",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "https://paper-beta-ten.vercel.app", "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(documents.router)
app.include_router(translation.router)
app.include_router(preferences.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "Paper Translator API"}
