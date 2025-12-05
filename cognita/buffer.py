"""# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial"""
from __future__ import annotations

"""Simple byte buffer with metadata and a read cursor."""

from typing import Any, Dict, Optional


class Buffer:
    """Minimal buffer abstraction carrying bytes plus metadata."""

    def __init__(self, data: bytes, meta: Optional[Dict[str, Any]] = None):
        self._data = data
        self._pos = 0
        self.meta = meta or {}

    def read(self, size: int | None = None) -> bytes:
        """Return up to `size` bytes (or the remainder if None) and advance the cursor."""
        if size is None or size < 0:
            size = len(self._data) - self._pos
        end = min(self._pos + size, len(self._data))
        chunk = self._data[self._pos : end]
        self._pos = end
        return chunk

    @property
    def remaining(self) -> int:
        """Bytes left unread."""
        return len(self._data) - self._pos

    def rewind(self) -> None:
        """Reset cursor to the start."""
        self._pos = 0
