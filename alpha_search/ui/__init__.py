"""UI module for Alpha Search - Streamlit application."""

try:
    from alpha_search.ui.streamlit_app import main as streamlit_main
except ImportError:  # pragma: no cover
    streamlit_main = None  # type: ignore
