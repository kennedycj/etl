"""Database connection management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Base class for declarative models
Base = declarative_base()


def create_database_engine(database_url: str):
    """Create SQLAlchemy engine from database URL."""
    return create_engine(database_url, echo=False)


def create_session_factory(engine):
    """Create session factory from engine."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session(engine):
    """Get a database session."""
    Session = create_session_factory(engine)
    return Session()

