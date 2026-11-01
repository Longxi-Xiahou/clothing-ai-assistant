"""Shared test-only environment configuration."""

import os


# Settings validates MYSQL_PASSWORD during import. Tests use mocked or
# in-memory database access, so provide a process-local placeholder only.
os.environ.setdefault("MYSQL_PASSWORD", "pytest-placeholder")
