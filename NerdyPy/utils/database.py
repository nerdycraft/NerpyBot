"""providing access to the sqlite db"""

from sqlalchemy import create_engine
from contextlib import contextmanager
from utils.errors import NerpyException
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base

BASE = declarative_base()
DBPATH = "sqlite:///db.db"

ENGINE = create_engine(DBPATH, echo=False)
SESSION = sessionmaker(bind=ENGINE)


def create_all():
    """ creates all tables previously defined"""
    BASE.metadata.bind = ENGINE
    BASE.metadata.create_all()


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = SESSION()
    error = None
    try:
        yield session
        session.commit()
    except SQLAlchemyError as ex:
        session.rollback()
        error = ex
    finally:
        session.close()

    if error is not None:
        raise NerpyException(error)
