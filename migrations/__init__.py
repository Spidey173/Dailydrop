"""
Database Migrations Package for Daily Drop.
"""


def run_migrations(*args, **kwargs):
    from .runner import run_migrations as _run
    return _run(*args, **kwargs)


def get_applied_migrations(*args, **kwargs):
    from .runner import get_applied_migrations as _get
    return _get(*args, **kwargs)


__all__ = ['run_migrations', 'get_applied_migrations']
