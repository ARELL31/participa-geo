"""FastAPI dependencies shared by the read routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session


def get_session(request: Request):
    """Yield a read-only ``Session`` bound to the app's ``api``-role engine."""
    session = Session(request.app.state.api_engine, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()


#: Dependency alias used by the read routes (keyword-only ``session`` argument).
SessionDep = Annotated[Session, Depends(get_session)]


__all__ = ["SessionDep", "get_session"]
