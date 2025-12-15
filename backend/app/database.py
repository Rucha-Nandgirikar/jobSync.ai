from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import QueuePool
import logging
from typing import List, Dict, Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Create engine with connection pooling
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

# Test connection on startup
def test_connection():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info("✅ Database connection successful")
            return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False

# Raw SQL execution utilities
def execute_query(query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Execute a SELECT query and return results as list of dicts"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            return [dict(row._mapping) for row in result]
    except Exception as e:
        logger.error(f"Query execution error: {e}")
        raise

def execute_insert(query: str, params: Optional[Dict[str, Any]] = None) -> int:
    """Execute INSERT query and return last insert ID"""
    try:
        with engine.begin() as conn:
            result = conn.execute(text(query), params or {})
            conn.commit()
            return result.lastrowid
    except Exception as e:
        logger.error(f"Insert execution error: {e}")
        raise

def execute_update(query: str, params: Optional[Dict[str, Any]] = None) -> int:
    """Execute UPDATE query and return affected rows"""
    try:
        with engine.begin() as conn:
            result = conn.execute(text(query), params or {})
            conn.commit()
            return result.rowcount
    except Exception as e:
        logger.error(f"Update execution error: {e}")
        raise

def execute_delete(query: str, params: Optional[Dict[str, Any]] = None) -> int:
    """Execute DELETE query and return affected rows"""
    try:
        with engine.begin() as conn:
            result = conn.execute(text(query), params or {})
            conn.commit()
            return result.rowcount
    except Exception as e:
        logger.error(f"Delete execution error: {e}")
        raise

def get_connection():
    """Get a database connection"""
    return engine.connect()


