"""
Database Session Management

Provides SQLAlchemy engine and session factories.

Uses Supabase PostgreSQL as the database backend.
Connection string format: postgresql://postgres.[project-ref]:[password]@[host]:6543/postgres
"""

import os
from typing import Generator, AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, Session

# Database URL from environment (Supabase PostgreSQL)
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://localhost:5432/mock_trial_ai"
)

# Async database URL (replace postgresql:// with postgresql+asyncpg://)
ASYNC_DATABASE_URL = DATABASE_URL.replace(
    "postgresql://",
    "postgresql+asyncpg://"
)

# Supabase requires SSL for external connections
# Check if we're connecting to Supabase (pooler.supabase.com)
IS_SUPABASE = "supabase" in DATABASE_URL.lower()


# =============================================================================
# SYNC ENGINE AND SESSION
# =============================================================================

# Configure connection args for Supabase SSL
connect_args = {}
if IS_SUPABASE:
    # Supabase requires SSL mode
    connect_args["sslmode"] = "require"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Enable connection health checks
    pool_size=5,
    max_overflow=10,
    echo=os.environ.get("SQL_ECHO", "false").lower() == "true",
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI to get a database session.
    
    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =============================================================================
# ASYNC ENGINE AND SESSION
# =============================================================================

# Only create async engine if asyncpg is available
try:
    # Configure async connection args for Supabase SSL
    async_connect_args = {}
    if IS_SUPABASE:
        async_connect_args["ssl"] = "require"
    
    async_engine = create_async_engine(
        ASYNC_DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        echo=os.environ.get("SQL_ECHO", "false").lower() == "true",
        connect_args=async_connect_args,
    )
    
    AsyncSessionLocal = sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
        """
        Async dependency for FastAPI to get a database session.
        """
        async with AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()

except ImportError:
    # asyncpg not installed, async not available
    async_engine = None
    AsyncSessionLocal = None
    
    async def get_async_db():
        raise NotImplementedError(
            "Async database sessions require asyncpg. "
            "Install with: pip install asyncpg"
        )


# =============================================================================
# INITIALIZATION
# =============================================================================

def init_db() -> None:
    """
    Initialize database connection.
    
    Call this at application startup to verify connection.
    Works with both local PostgreSQL and Supabase.
    """
    from sqlalchemy import text
    from .models import Base
    
    # Test connection
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    
    db_type = "Supabase" if IS_SUPABASE else "PostgreSQL"
    # Hide credentials in log output
    safe_url = DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL
    print(f"{db_type} connected: {safe_url}")


def create_tables() -> None:
    """
    Create all database tables.
    
    Call this for initial setup or development.
    For production, use Alembic migrations.
    """
    from .models import Base
    
    Base.metadata.create_all(bind=engine)
    print("Database tables created")


def drop_tables() -> None:
    """
    Drop all database tables.
    
    WARNING: This deletes all data! Use only in development.
    """
    from .models import Base
    
    Base.metadata.drop_all(bind=engine)
    print("Database tables dropped")
