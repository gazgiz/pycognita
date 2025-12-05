"""# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial"""
from __future__ import annotations

"""Element that generates a detailed English description for image caps using Ollama."""

import base64
import os

from .caps import Caps
from .element import Element
from .ollama import OllamaClient, OllamaError
from .pad import PadDirection


TEXT_CAPS = Caps(
    media_type="text/plain",
    name="plain-text",
    description="Plain text produced by ImageNarrator.",
    extensions=("txt",),
    uri="urn:cognita:caps:plain-text",
    broader=("urn:cognita:category:content",),
)


class ImageNarrator(Element):
    """Consumes buffers, and for image-photo caps, asks Ollama to describe the image."""

    def __init__(self, ollama_client: OllamaClient | None = None):
        super().__init__()
        # Default to a vision-capable model if none is provided.
        self.ollama_client = ollama_client or OllamaClient(model="qwen2.5vl:3b")
        self._caps: Caps | None = None

    def process(self) -> None:
        # No-op: work is reactive in on_buffer.
        return

    def handle_event(self, pad, event: str, payload: object | None = None) -> None:
        if event == "caps":
            if not isinstance(payload, Caps):
                raise TypeError("ImageNarrator caps event requires Caps payload")
            pad.caps = payload
            self._caps = payload
            # Forward caps downstream.
            for peer in (p for p in self.pads if p.direction == PadDirection.SRC and p.peer):
                peer.peer.caps = payload
                peer.peer.element.handle_event(peer.peer, event, payload)
            return
        return super().handle_event(pad, event, payload)

    def on_buffer(self, pad, payload: object) -> None:
        caps = self._caps or getattr(pad, "caps", None)
        
        # If caps are present but not for a photo, pass through.
        if isinstance(caps, Caps) and caps.name != "image-photo":
            self._push_downstream(payload)
            return

        # If no caps and no URI, we can't proceed.
        if not isinstance(caps, Caps):
            if not isinstance(payload, dict) or "uri" not in payload:
                raise RuntimeError("ImageNarrator requires caps or URI payload")

        if not isinstance(payload, dict):
            self._push_downstream(payload)
            return

        description = self._describe_image(payload.get("data"), payload.get("uri"))
        self._announce_text_caps()
        self._push_downstream(description)

    def _describe_image(self, data: bytes | None, uri: str | None) -> str:
        if not self.ollama_client:
            return "No Ollama client configured; image description unavailable."

        #if data is None and uri:
        data = self._read_all(uri)
        if not data:
            return "Image bytes unavailable; cannot generate description."

        b64 = base64.b64encode(data).decode("ascii")
        prompt = (
            "You are an image description assistant. "
            "Given a full image encoded in base64, write a detailed English description "
            "of what the image contains. Include salient objects, people, setting, colors, and mood. "
            "Write multiple sentences if needed, aiming for thoroughness without fluff.\n"
            f"Image URI: {uri or 'unknown'}\n"
            f"Base64 (entire image): {b64}\n"
            "Provide the description only."
        )
        try:
            return self.ollama_client._request(prompt)  # uses existing text generation endpoint
        except OllamaError as error:
            return f"[ollama error] {error}"

    def _read_all(self, uri: str) -> bytes:
        path = uri[len("file://") :] if uri.startswith("file://") else uri
        if not os.path.isfile(path):
            return b""
        with open(path, "rb") as file:
            return file.read()

    def _push_downstream(self, payload: object) -> None:
        for pad in self.pads:
            if pad.direction == PadDirection.SRC and pad.peer:
                pad.peer.element.on_buffer(pad.peer, payload)

    def _announce_text_caps(self) -> None:
        self._caps = TEXT_CAPS
        for pad in self.pads:
            if pad.direction == PadDirection.SRC:
                pad.set_caps(TEXT_CAPS, propagate=True)
