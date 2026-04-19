"""Load project-root .env before reading os.environ (proxy + optional paths)."""

from __future__ import annotations

import os
from pathlib import Path


def _project_root_for_env() -> Path:
    override = os.getenv("ZILLOW_DATA_DIR")
    if override:
        return Path(override)
    here = Path(__file__).resolve()
    dev_root = here.parents[2]
    if (dev_root / "pyproject.toml").is_file():
        return dev_root
    return Path.cwd()


def load_project_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    path = _project_root_for_env() / ".env"
    if path.is_file():
        load_dotenv(path, override=False)
