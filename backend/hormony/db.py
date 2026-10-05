from sqlalchemy import create_engine, text, update
from sqlalchemy.exc import ArgumentError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def _redact(url: str) -> str:
    """Hide the password part of a database URL for error messages."""
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        return f"{scheme}://***@{rest.split('@', 1)[1]}"
    return url


def _make_engine(url: str):
    try:
        if url.startswith("sqlite"):
            return create_engine(url, connect_args={"check_same_thread": False})
        return create_engine(url, pool_pre_ping=True)
    except (ArgumentError, ModuleNotFoundError) as e:
        raise RuntimeError(f"Invalid HORMONY_DATABASE_URL {_redact(url)!r}: {e}") from None


engine = _make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models
    from .ledger.cycle import LEGACY_TYPES
    try:
        Base.metadata.create_all(bind=engine)
        with engine.begin() as conn:  # earlier builds stored short type codes; normalise them once
            for old, new in LEGACY_TYPES.items():
                conn.execute(update(models.Event).where(models.Event.type == old).values(type=new))
    except SQLAlchemyError as e:
        raise RuntimeError(f"Cannot open the database at {_redact(settings.database_url)}: "
                           f"{e.__class__.__name__}: {e.args[0] if e.args else e}") from None


def db_ok() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False
