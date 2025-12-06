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
class TimeSeriesDataSource(SourceElement):
    """Streaming data source (e.g. logs, sensors) that must prebuffer for type detection.
    
    Because the data is a stream (destructive read), the bytes read for detection
    MUST be preserved and passed downstream so no data is lost.
    
    Payload:
        - type_source: "header" or "ollama"
        - uri: Source URI
        - data: The prebuffered initial bytes
    """

    uri: str
    prebuffer_bytes: int = 65_535
    header_analyzer: HeaderAnalyzer | None = None
    ollama_client: OllamaClient | None = None

    def __post_init__(self) -> None:
        super().__init__()
        if self.header_analyzer is None:
            self.header_analyzer = HeaderAnalyzer()

    def _read_prebuffer(self) -> bytes:
        if self.uri.startswith("file://"):
            path = self.uri[len("file://") :]
        else:
            path = self.uri
            
        if not os.path.isfile(path):
            raise FileNotFoundError(f"resource does not exist: {self.uri}")
        with open(path, "rb") as file:
            return file.read(self.prebuffer_bytes)

    def process(self) -> None:
        """Read prebuffer, detect type, and push payload with data."""
        data = self._read_prebuffer()
        caps, type_source = _detect_caps(
            data, self.uri, self.header_analyzer, self.ollama_client
        )

        payload = {"type_source": type_source, "uri": self.uri, "data": data}
        for pad in self.pads:
            if pad.direction == PadDirection.SRC:
                pad.set_caps(caps, propagate=True)
                pad.push(payload)


@dataclass
class DiscreteDataSource(SourceElement):
    """Discrete data source (e.g. files) that performs detection but passes only URI.
    
    Because the data is random-access/static, we can read a sample for detection
    and discard it. Downstream elements will open the URI themselves.
    
    Payload:
        - type_source: "header" or "ollama"
        - uri: Source URI
        # No 'data' field; downstream reads from 'uri'
    """

    uri: str
    header_analyzer: HeaderAnalyzer | None = None
    ollama_client: OllamaClient | None = None
    
    _DETECTION_SAMPLE_SIZE = 32_768  # 32KB sample for detection

    def __post_init__(self) -> None:
        super().__init__()
        if self.header_analyzer is None:
            self.header_analyzer = HeaderAnalyzer()

    def _read_detection_sample(self) -> bytes:
        if self.uri.startswith("file://"):
            path = self.uri[len("file://") :]
        else:
            path = self.uri
            
        if not os.path.isfile(path):
            raise FileNotFoundError(f"resource does not exist: {self.uri}")
        
        try:
            with open(path, "rb") as file:
                return file.read(self._DETECTION_SAMPLE_SIZE)
        except OSError as e:
            raise e

    def process(self) -> None:
        """Read sample, detect type, and push payload without data."""
        data = self._read_detection_sample()
        caps, type_source = _detect_caps(
            data, self.uri, self.header_analyzer, self.ollama_client
        )

        payload = {"type_source": type_source, "uri": self.uri}
        for pad in self.pads:
            if pad.direction == PadDirection.SRC:
                pad.set_caps(caps, propagate=True)
                pad.push(payload)


def _detect_caps(
    data: bytes,
    uri: str,
    header_analyzer: HeaderAnalyzer,
    ollama_client: OllamaClient | None
) -> tuple[object | None, str]: # Changed Caps to object to avoid import issues
    """Shared logic for detecting caps from data sample."""
    caps = header_analyzer.detect(data)
    type_source = "header"
    
    if not caps:
        if not ollama_client:
            raise TypeFinderError("Unknown format; Ollama fallback not configured")
        try:
            caps = ollama_client.guess_file_type(
                file_path=uri,
                header_hex=header_sample_to_hex(data),
                body_preview=preview_text(data),
            )
            type_source = "ollama"
        except Exception as error:
            raise TypeFinderError(f"Ollama error: {error}") from error
            
    return caps, type_source
