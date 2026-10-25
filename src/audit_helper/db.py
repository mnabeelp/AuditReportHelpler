"""Database engine management (per-company SQLite)."""
import os
from pathlib import Path
from typing import Dict
from sqlmodel import SQLModel, create_engine, Session

_ENGINES: Dict[str, object] = {}

DEFAULT_DATA_DIR = os.getenv("DATA_DIR", "./data")


def db_path_for(company: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in company)
    d = Path(DEFAULT_DATA_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return str(d / f"{safe or 'default'}.db")


def get_engine(company: str = "default"):
    if company in _ENGINES:
        return _ENGINES[company]
    url = f"sqlite:///{db_path_for(company)}"
    engine = create_engine(url, echo=False)
    SQLModel.metadata.create_all(engine)
    _ENGINES[company] = engine
    return engine


def get_session(company: str = "default") -> Session:
    return Session(get_engine(company))


def list_companies() -> list[str]:
    d = Path(DEFAULT_DATA_DIR)
    if not d.exists():
        return []
    return [p.stem for p in d.glob("*.db")]
