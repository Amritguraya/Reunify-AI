"""Production WSGI entry point."""

import os

os.environ["APP_ENV"] = "production"

from app import app  # noqa: E402

