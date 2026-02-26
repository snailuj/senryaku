from sqlmodel import Session, SQLModel, create_engine

from senryaku.config import get_settings

settings = get_settings()

# SQLite needs check_same_thread=False for FastAPI
engine = create_engine(
    f"sqlite:///{settings.db_path}",
    connect_args={"check_same_thread": False},
    echo=False,
)


def init_db():
    """Create all tables. Used for dev/testing. Production uses Alembic."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency that yields a database session."""
    with Session(engine) as session:
        yield session
