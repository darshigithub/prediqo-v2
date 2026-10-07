from pathlib import Path

# backend/app/core/config.py -> parents: [core, app, backend, project root]
BASE_DIR = Path(__file__).resolve().parents[2]   # backend/
ROOT_DIR = Path(__file__).resolve().parents[3]   # project root

# Storage: local files only
DATA_DIR = ROOT_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
DATASETS_DIR = DATA_DIR / "datasets"   # parquet files
METADATA_DIR = DATA_DIR / "metadata"   # JSON metadata, dashboards
CACHE_DIR = DATA_DIR / "cache"
QUERY_CACHE_DIR = CACHE_DIR / "query"
JOBS_DIR = DATA_DIR / "jobs"
MODELS_DIR = DATA_DIR / "models"       # trained ML models and metadata


for d in (UPLOADS_DIR, DATASETS_DIR, METADATA_DIR, CACHE_DIR, QUERY_CACHE_DIR, JOBS_DIR, MODELS_DIR):
    d.mkdir(parents=True, exist_ok=True)

DATASETS_INDEX = METADATA_DIR / "datasets_index.json"

# Optional AI provider (not required for the prototype)
OPENAI_API_KEY = None  # set via env var OPENAI_API_KEY at runtime if available