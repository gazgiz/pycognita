"""# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial"""
from __future__ import annotations

"""Sink elements for the pipeline."""

from .caps import Caps, summarize_caps
from .element import SinkElement
from .pad import PadDirection


class SilentSink(SinkElement):
    """Terminal sink that records upstream payload (caps info) without further processing."""

    def __init__(self) -> None:
        super().__init__()
        self.outputs: list[str] = []

    def process(self) -> None:
        return

    @property
    def output(self) -> str | None:
        if not self.outputs:
            return None
        return "\n".join(self.outputs)

    def on_buffer(self, pad, payload: object) -> None:
        caps = getattr(pad, "caps", None)
        if not isinstance(caps, Caps):
            raise RuntimeError("SilentSink requires upstream pad caps")
        # Prefer direct text payload (e.g., from ImageNarrator) or narration field.
        if isinstance(payload, str):
            self.outputs.append(payload)
            return
        if isinstance(payload, dict) and payload.get("image_description"):
            self.outputs.append(payload["image_description"])
            return
        type_source = payload.get("type_source") if isinstance(payload, dict) else None
        self.outputs.append(summarize_caps(caps, type_source=type_source))
