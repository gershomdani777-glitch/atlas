from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config import settings

# Conservative pool sizing against Supabase's transaction-mode pooler
# (Supavisor, port 6543), which caps backend connections per project far
# below SQLAlchemy's own defaults (pool_size=5 + max_overflow=10 = 15).
# pool_recycle keeps connections from going stale past the pooler's own
# idle-connection timeout, which otherwise surfaces as a hard-to-diagnose
# "server closed the connection unexpectedly" on reuse.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=3,
    max_overflow=2,
    pool_recycle=280,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
