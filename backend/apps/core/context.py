"""
Which society (tenant) is the current request working for?

A ContextVar is like a global variable that is private to each request, so two
requests from two different societies never see each other's value.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.societies.models import Society

_current_society: ContextVar[Society | None] = ContextVar("current_society", default=None)


def get_current_society() -> Society | None:
    return _current_society.get()


def set_current_society(society: Society | None):
    """Set the society and return a token that can restore the previous value."""
    return _current_society.set(society)


def reset_current_society(token) -> None:
    _current_society.reset(token)


@contextmanager
def use_society(society: Society | None):
    """Run a block of code as a given society, e.g. in a Celery task or a test."""
    token = set_current_society(society)
    try:
        yield
    finally:
        reset_current_society(token)
