"""API module for Alpha Search - FastAPI application."""

try:
    from alpha_search.api.app import create_app
except ImportError:
    create_app = None  # type: ignore
