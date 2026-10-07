"""AI Analytics Prototype — FastAPI entrypoint.

Run:  uvicorn app.main:app --reload --port 8000
"""
from pathlib import Path
from dotenv import load_dotenv

# Load .env from backend/.env or parent .env
backend_dir = Path(__file__).resolve().parents[1]
load_dotenv(backend_dir / ".env")
load_dotenv(backend_dir.parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router

app = FastAPI(title="AI Analytics Prototype", version="0.1.0")

# Vite dev server default port
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {"service": "AI Analytics Prototype API", "docs": "/docs"}
