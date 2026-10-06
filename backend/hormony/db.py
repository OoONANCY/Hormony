from sqlalchemy import create_engine, inspect, select, text, update
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


def migrate_event_keys(eng) -> None:
    """Earlier builds keyed records by `id` alone, so two people logging the same thing on the same day collided.
    Move the primary key to (patient_id, id), keeping every row."""
    from .models import Event
    _rekey(eng, Event.__table__)


def _rekey(eng, table) -> None:
    insp = inspect(eng)
    name = table.name
    if name not in insp.get_table_names() or insp.get_pk_constraint(name)["constrained_columns"] != ["id"]:
        return
    if eng.dialect.name != "sqlite":
        pk = insp.get_pk_constraint(name)["name"]
        with eng.begin() as conn:
            conn.execute(text(f'ALTER TABLE {name} DROP CONSTRAINT "{pk}"'))
            conn.execute(text(f"ALTER TABLE {name} ADD PRIMARY KEY (patient_id, id)"))
        return
    old_cols = {c["name"] for c in insp.get_columns(name)}
    cols = ", ".join(c.name for c in table.columns if c.name in old_cols)
    with eng.begin() as conn:  # SQLite can't change a primary key in place: rebuild the table in one transaction
        for ix in insp.get_indexes(name):
            conn.execute(text('DROP INDEX "{}"'.format(ix["name"])))
        conn.execute(text(f"ALTER TABLE {name} RENAME TO {name}_old"))
        table.create(bind=conn)
        conn.execute(text(f"INSERT INTO {name} ({cols}) SELECT {cols} FROM {name}_old"))
        conn.execute(text(f"DROP TABLE {name}_old"))


def init_db() -> None:
    from . import models
    from .ledger.cycle import LEGACY_TYPES
    try:
        Base.metadata.create_all(bind=engine)
        migrate_event_keys(engine)
        with engine.begin() as conn:  # earlier builds stored short type codes; normalise them once
            for old, new in LEGACY_TYPES.items():
                conn.execute(update(models.Event).where(models.Event.type == old).values(type=new))
        with engine.connect() as conn:  # ledgers seeded before profiles existed: give the demo patient its profile
            has_demo = conn.execute(select(models.Event.id).where(models.Event.patient_id == "nancy").limit(1)).first()
        if has_demo:
            from .ledger.profiles import ensure_demo_profile
            ensure_demo_profile()
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
