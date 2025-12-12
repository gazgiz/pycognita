# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial
"""Element that generates a detailed English description for image caps using Ollama."""

from __future__ import annotations

import base64
import os

from .caps import Caps
from .narrator import Narrator
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

        # if data is None and uri:
        data = self._read_all(uri)
        if not data:
            return "Image bytes unavailable; cannot generate description."

        b64 = base64.b64encode(data).decode("ascii")
        prompt = (
            "Analyze this image to provide structured data for a Knowledge Graph using a 'Chain of Description' method.\n"
            "Step 1: Identify the Overall Situation. What is happening globally? (e.g., 'A busy commute at a train station').\n"
            "Step 2: Justify your identification. Why is it this situation? (e.g., 'Because I see a [Crowd] waiting near the [Ticket Gates]').\n"
            "Step 3: Drill down into the entities mentioned. Describe them and their states.\n"
            "   - 'The [Crowd] is dense and moving towards the platform.'\n"
            "   - 'The [Ticket Gates] are open and metallic.'\n"
            "Step 4: Continue drilling down until no meaningful details remain.\n"
            "Step 5: Output strictly as a list of atomic statements (Subject - Predicate - Object format).\n"
            "Format rules:\n"
            "- Start with: 'This image depicts [Situation/Context].'\n"
            "- [Subject] [predicate] [Object]\n"
            "- CRITICAL: Do NOT repeat the same action for multiple individuals (e.g., NO 'Person 1 is entering', 'Person 2 is entering'). Group them: 'Crowd is entering'.\n"
            "Example:\n"
            "- This image depicts a Graduation Ceremony.\n"
            "- Graduation Ceremony involves Graduates and Audience.\n"
            "- Graduates are wearing Cap and Gown.\n"
            "- Audience is sitting in Bleachers.\n"
            "Do NOT write paragraphs. List separate facts."
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
