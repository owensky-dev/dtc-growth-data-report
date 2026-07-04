from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORTS_DIR = PROJECT_ROOT / "reports"


def setup_logging(name: str) -> logging.Logger:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    return logging.getLogger(name)


def load_dotenv(path: Path | None = None) -> None:
    env_path = path or PROJECT_ROOT / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_settings(required: list[str] | None = None) -> dict[str, str]:
    load_dotenv()
    settings = dict(os.environ)
    missing = [key for key in required or [] if not settings.get(key)]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"Missing required configuration: {joined}. Add it to .env or your local environment."
        )
    return settings


def ensure_dirs() -> None:
    for path in (DATA_RAW_DIR, DATA_PROCESSED_DIR, REPORTS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def default_date_range(days: int = 90) -> tuple[str, str]:
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    return start.isoformat(), end.isoformat()


def normalize_url(value: str | None, base_url: str | None = None) -> str:
    if not value:
        return ""

    text = str(value).strip()
    if not text:
        return ""

    if text.startswith("/"):
        text = urljoin((base_url or "").rstrip("/") + "/", text.lstrip("/"))

    parsed = urlparse(text)
    if not parsed.netloc and base_url:
        text = urljoin(base_url.rstrip("/") + "/", text)
        parsed = urlparse(text)

    cleaned = parsed._replace(fragment="")
    return urlunparse(cleaned)


def require_any(keys: list[str], purpose: str) -> str:
    settings = load_settings()
    for key in keys:
        if settings.get(key):
            return settings[key]
    raise RuntimeError(
        f"Missing configuration for {purpose}. Provide one of: {', '.join(keys)}."
    )
