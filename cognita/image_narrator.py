"""# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial"""
from __future__ import annotations

"""Element that generates a detailed English description for image caps using Ollama."""

import base64
import os

from .caps import Caps
from .narrator import Narrator, TEXT_CAPS
from .ollama import OllamaClient, OllamaError


class ImageNarrator(Narrator):
    """Consumes buffers, and for image-photo caps, asks Ollama to describe the image.
    
    Like MailboxNarrator, this supports both capped and uncapped (URI-only) payloads.
    It uses a vision-capable Ollama model (default: qwen2.5vl:3b) to generate descriptions.
    """

    def __init__(self, ollama_client: OllamaClient | None = None):
        super().__init__()
        # Default to a vision-capable model if none is provided.
        self.ollama_client = ollama_client or OllamaClient(model="qwen2.5vl:3b")

    def _can_process(self, caps: Caps | None, payload: object) -> bool:
        # 1. Capped mode: strictly check for image-photo.
        if isinstance(caps, Caps):
            return caps.name == "image-photo"
        
        # 2. Uncapped mode: check if we have a URI.
        # Note: We don't strictly verify file content here like MailboxNarrator does,
        # because we rely on Ollama to handle (or reject) the image data later.
        # This is a design choice: we could add _is_image() checks here if we wanted
        # to be stricter.
        return isinstance(payload, dict) and "uri" in payload

    def _narrate(self, payload: object, caps: Caps | None) -> str | None:
        """Generate a description of the image using Ollama."""
        if not isinstance(payload, dict):
            return None

        # Extract data (if prebuffered) or read from URI.
        return self._describe_image(payload.get("data"), payload.get("uri"))

    def _describe_image(self, data: bytes | None, uri: str | None) -> str:
        if not self.ollama_client:
            return "No Ollama client configured; image description unavailable."

        #if data is None and uri:
        data = self._read_all(uri)
        if not data:
            return "Image bytes unavailable; cannot generate description."

        b64 = base64.b64encode(data).decode("ascii")
        prompt = (
            "Analyze this image for Knowledge Graph extraction. "
            "Identify distinct objects and their inter-relationships. "
            "Output strictly as a list of atomic statements in this format:\n"
            "- [Object A] [relationship] [Object B]\n"
            "- [Object] is [Visual Attribute]\n"
            "Example: '- PlasticBag contains Mulberries', '- Mulberries are Purple'.\n"
            "Do NOT write paragraphs. Do NOT use generic terms like 'Image has object...'. "
            "List separate facts."
        )
        try:
            return self.ollama_client._request(prompt, images=[b64])  # Pass image separately
        except OllamaError as error:
            return f"[ollama error] {error}"

    def _read_all(self, uri: str) -> bytes:
        path = uri[len("file://") :] if uri.startswith("file://") else uri
        if not os.path.isfile(path):
            return b""
        with open(path, "rb") as file:
            return file.read()
