"""ASGI entrypoint: `uvicorn backend.main:app`."""
from backend.main import app

__all__ = ["app"]
