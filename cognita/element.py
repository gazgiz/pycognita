# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial
"""Base Element class for pipeline processing steps.

Minimal GStreamer-inspired element model with dynamic pads only.

Intent:
  - Keep the data path explicit: pads link elements, buffers travel via `on_buffer`.
  - Keep control/negotiation explicit: events travel via `handle_event` (e.g., caps).
  - Keep roles clear: sources emit on src pads, sinks consume on sink pads.

Defined here:
  - PadDirection: src/sink role marker.
  - Pad: linkable endpoint owned by an element (pads do NOT store buffers).
  - Element: base class with hooks for buffers and events.
  - SourceElement / SinkElement: role-constrained variants of Element.
"""

from __future__ import annotations

from .caps import Caps
from .pad import Pad, PadDirection


class CapsNegotiationError(Exception):
    """Raised when elements cannot agree on Caps."""


class Element:
    """Base processing element with dynamic pads.

    Responsibilities:
      - Own pads and create them dynamically (`request_pad`).
      - Emit work in `process` (typically sources kick off push-mode).
      - React to data via `on_buffer` on sink pads.
      - React to control/negotiation via `handle_event` (caps, etc).
    """

    def __init__(self) -> None:
        self._pads: list[Pad] = []

    def request_pad(self, direction: PadDirection, name: str | None = None) -> Pad:
        """Create a new dynamic pad.

        Elements can override to reject certain directions. Pads are named
        sequentially by direction when no explicit name is provided.
        """
        pad_name = name or f"{direction.value}{len(self._pads)}"
        pad = Pad(pad_name, direction, self)
        self._pads.append(pad)
        return pad

    @property
    def pads(self) -> list[Pad]:
        """Return a shallow copy of pads to avoid external mutation."""
        return list(self._pads)

    def process(self) -> None:  # pragma: no cover - base hook
        raise NotImplementedError

    def on_buffer(self, pad: Pad, buffer: object) -> None:  # pragma: no cover - base hook
        """Handle a buffer arriving on a sink pad."""
        raise NotImplementedError

    def handle_event(
        self, pad: Pad, event: str, payload: object | None = None
    ) -> None:  # pragma: no cover - base hook
        """Handle a generic pad event (e.g., caps negotiation).

        Raises:
            CapsNegotiationError: If incompatible caps are received.
        """
        if event == "caps":
            if not isinstance(payload, Caps):
                raise TypeError("caps event requires Caps payload")
            pad.caps = payload
            return
        raise NotImplementedError(f"unhandled event: {event}")

    def send_event(self, event: str, payload: object | None = None) -> None:
        """Emit an event downstream on all src pads."""
        for pad in self._pads:
            if pad.direction == PadDirection.SRC and pad.peer:
                pad.peer.element.handle_event(pad.peer, event, payload)


class SourceElement(Element):
    """Element with one or more output pads and no inputs."""

    def request_pad(self, direction: PadDirection, name: str | None = None) -> Pad:
        if direction != PadDirection.SRC:
            raise ValueError("SourceElement only provides src pads")
        return super().request_pad(direction, name)


class SinkElement(Element):
    """Element with one or more input pads and no outputs."""

    def request_pad(self, direction: PadDirection, name: str | None = None) -> Pad:
        if direction != PadDirection.SINK:
            raise ValueError("SinkElement only provides sink pads")
        return super().request_pad(direction, name)
