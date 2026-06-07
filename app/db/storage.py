"""Supabase Storage access (isolated so the rest of the app stays testable).

Only used by the by-reference analysis path. ``supabase`` is imported lazily so the
dependency isn't required for the multipart upload path or for tests that mock this.
"""

from __future__ import annotations

import os
import tempfile

from app.config import Settings
from app.errors import StorageDownloadError


def download_to_temp(bucket: str, path: str, settings: Settings) -> str:
    """Download an object from Supabase Storage to a temp file; return its path.

    Uses the server-only service-role key (never exposed to clients). Raises
    :class:`StorageDownloadError` on misconfiguration or failure.
    """
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise StorageDownloadError(
            "Supabase Storage is not configured (missing URL or service-role key)."
        )

    from supabase import create_client

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        data = client.storage.from_(bucket).download(path)
    except Exception as exc:  # supabase raises various client errors
        raise StorageDownloadError(
            f"Could not download '{path}' from bucket '{bucket}': {exc}"
        ) from exc

    suffix = os.path.splitext(path)[1] or ".mp4"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as out:
        out.write(data)
    return tmp_path
