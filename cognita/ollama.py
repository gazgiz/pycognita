"""# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial"""
from __future__ import annotations

"""Minimal Ollama client for file-type guessing.

This module keeps HTTP and parsing logic small and dependency-free:
  - Uses stdlib urllib for POSTing prompts to an Ollama server.
  - Accepts a friendly JSON shape from the model and maps it to `Caps`.
  - Surfaces narrow exception types to keep pipeline error handling clear.

The client is intentionally synchronous and single-purpose; callers can build
their own retry/timeout logic around it if needed.
"""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict

from .caps import Caps


class OllamaError(RuntimeError):
    """Base exception for Ollama client failures."""


class OllamaUnavailableError(OllamaError):
    """Raised when the Ollama endpoint cannot be reached (network/refused)."""


def _extract_json_object(text: str) -> Dict[str, Any] | None:
    """Best-effort extraction of a JSON object from a free-form string."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


@dataclass
class OllamaClient:
    """Very small client wrapper for the Ollama HTTP API."""

    model: str = "llama3.1"
    base_url: str = "http://localhost:11434"
    timeout: int = 10

    def _request(self, prompt: str, images: list[str] | None = None) -> str:
        """Send a prompt to the Ollama generate endpoint and return raw body."""
        url = f"{self.base_url.rstrip('/')}/api/generate"
        payload_dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if images:
            payload_dict["images"] = images

        payload = json.dumps(payload_dict).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.URLError as error:
            raise OllamaUnavailableError(error.reason) from error
        except Exception as error:
            raise OllamaError(str(error)) from error

        try:
            data = json.loads(body)
            return data.get("response") or body
        except json.JSONDecodeError:
            return body

    def guess_file_type(self, file_path: str | None, header_hex: str, body_preview: str) -> Caps:
        """Ask Ollama to classify a file based on header hex and preview text."""
        prompt = self._build_prompt(file_path=file_path, header_hex=header_hex, body_preview=body_preview)
        response = self._request(prompt)
        parsed = _extract_json_object(response)
        if not parsed:
            raise OllamaError("Ollama returned a non-JSON answer")

        return Caps(
            media_type=parsed.get("mime_type", "application/octet-stream"),
            name=parsed.get("type_name", "unknown"),
            params={
                "description": parsed.get("rationale"),
                "extensions": tuple(parsed.get("extensions", ())) or None,
            },
        )

    def _build_prompt(self, file_path: str | None, header_hex: str, body_preview: str) -> str:
        """Compose a deterministic prompt for the file-type classification task."""
        file_label = file_path or "input file"
        return (
            "You are a file type classifier. "
            "Given hex header bytes and a short textual preview, identify the file type. "
            "Prefer coarse categories when appropriate: document, binary, image, video, mail, calendar. "
            "Respond with JSON in the form "
            '{"type_name": "...", "mime_type": "...", "extensions": ["ext1","ext2"], "rationale": "..."}.\n\n'
            f"File: {file_label}\n"
            f"Header (hex, first bytes): {header_hex}\n"
            f"Text preview (best-effort decoded): {body_preview}\n"
            "Be concise in rationale and prefer the safest guess if unsure."
        )
