"""# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial"""
from __future__ import annotations

"""Source element variants for time-series vs discrete data, using URI input."""

import os
from dataclasses import dataclass

from .element import SourceElement
from .ollama import OllamaClient
from .pad import PadDirection
from .type_finder import (
    HeaderAnalyzer,
    TypeFinderError,
    header_sample_to_hex,
    preview_text,
)


@dataclass
class PrebufferSource(SourceElement):
    """Common base for sources that prebuffer a fixed number of bytes.
    
    This source reads a chunk of data (prebuffer) from the URI at startup.
    It then uses a HeaderAnalyzer (and optionally Ollama) to detect the content type (Caps).
    Finally, it emits a payload containing:
    - type_source: How the type was detected ("header" or "ollama").
    - uri: The source URI.
    - data: The prebuffered bytes.
    """

    uri: str
    prebuffer_bytes: int = 65_535
    header_analyzer: HeaderAnalyzer | None = None
    ollama_client: OllamaClient | None = None

    def __post_init__(self) -> None:
        super().__init__()
        if self.header_analyzer is None:
            self.header_analyzer = HeaderAnalyzer()

    def set_prebuffer_bytes(self, size: int) -> None:
        """Configure how many bytes to prebuffer before emitting payloads."""
        if size < 0:
            raise ValueError("prebuffer_bytes must be non-negative")
        self.prebuffer_bytes = size

    def _read_prebuffer(self) -> bytes:
        path = self._uri_to_path(self.uri)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"resource does not exist: {self.uri}")
        with open(path, "rb") as file:
            return file.read(self.prebuffer_bytes) if self.prebuffer_bytes else file.read()

    @staticmethod
    def _uri_to_path(uri: str) -> str:
        if uri.startswith("file://"):
            return uri[len("file://") :]
        return uri

    def process(self) -> None:
        """Read data, detect type, and push payload downstream."""
        data = self._read_prebuffer()
        caps = self.header_analyzer.detect(data)
        type_source = "header"
        
        # Fallback to Ollama if header detection fails
        if not caps:
            if not self.ollama_client:
                raise TypeFinderError("Unknown format; Ollama fallback not configured")
            try:
                caps = self.ollama_client.guess_file_type(
                    file_path=self.uri,
                    header_hex=header_sample_to_hex(data),
                    body_preview=preview_text(data),
                )
                type_source = "ollama"
            except Exception as error:
                raise TypeFinderError(f"Ollama error: {error}") from error

        payload = {"type_source": type_source, "uri": self.uri, "data": data}
        for pad in self.pads:
            if pad.direction == PadDirection.SRC:
                pad.set_caps(caps, propagate=True)
                pad.push(payload)


class TimeSeriesDataSource(PrebufferSource):
    """Time-series oriented source (e.g., logs/sensor/CCTV feeds) with initial prebuffer.
    
    Currently identical to PrebufferSource, but semantically distinct.
    Future extensions might include streaming or chunked reading.
    """


@dataclass
class DiscreteDataSource(SourceElement):
    """Discrete data source (e.g., regular files/blob URIs) that passes URI downstream.
    
    Unlike PrebufferSource, this class does NOT read the file content or perform type detection.
    It simply emits a payload containing the URI. Downstream elements (like Narrators)
    are responsible for reading the content and determining if they can process it.
    
    This approach is more efficient for large files or when we only want to process
    specific file types (filtering is done by downstream elements).
    """

    uri: str

    def __post_init__(self) -> None:
        super().__init__()

    def process(self) -> None:
        """Emit URI payload downstream."""
        payload = {"uri": self.uri}
        for pad in self.pads:
            if pad.direction == PadDirection.SRC:
                pad.push(payload)
