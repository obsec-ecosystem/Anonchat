from pathlib import Path

FRONT_DIR = Path(__file__).resolve().parent
ROOT_DIR = FRONT_DIR.parent
UPLOAD_DIR = ROOT_DIR / "uploads"
TEMPLATES_DIR = FRONT_DIR / "templates"
STATIC_DIR = FRONT_DIR / "static"
MAX_UPLOAD_MB = 10
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
