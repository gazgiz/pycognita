# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial
"""Pad primitives shared across elements."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .element import Element


class PadDirection(str, Enum):
    """Direction of a pad.

    SRC pads emit data to a downstream peer; SINK pads receive data from an
    upstream peer. Mixed linking is enforced at runtime when pads connect.
    """

    SRC = "src"
    SINK = "sink"


class Pad:
    """Linkable endpoint owned by an Element.

    Pads are created dynamically, linked exactly once, and enforce that source
    pads only connect to sink pads. Elements own their pads, but the pad keeps a
    back-reference to its element to allow future flow-control extensions.
    """

    def __init__(self, name: str, direction: PadDirection, element: Element):
        self.name = name
        self.direction = direction
        self.element = element
        self.peer: Pad | None = None
        self.caps: Any | None = None  # Optional negotiated caps

    def link(self, peer: Pad) -> None:
        """Connect this pad to its peer, enforcing directionality and single-link rules."""
        if self.peer or peer.peer:
            raise ValueError("pad already linked")
        if self.direction == peer.direction:
            raise ValueError("pad directions must be opposite")
        if self.direction == PadDirection.SRC and peer.direction != PadDirection.SINK:
            raise ValueError("source pad must connect to sink pad")
        if self.direction == PadDirection.SINK and peer.direction != PadDirection.SRC:
            raise ValueError("sink pad must connect to source pad")
        self.peer = peer
        peer.peer = self

    def set_caps(self, caps: Any, propagate: bool = False) -> None:
        """Store caps on this pad and optionally propagate as an event downstream."""
        self.caps = caps
        if propagate and self.direction == PadDirection.SRC:
            self.send_caps(caps)

    def send_caps(self, caps: Any) -> None:
        """Send a caps event downstream to the linked sink pad (does not store)."""
        if self.direction != PadDirection.SRC:
            raise ValueError("send_caps is only valid on src pads")
        if not self.peer:
            raise ValueError("pad is not linked")
        return self.peer.element.handle_event(self.peer, "caps", caps)

    def push(self, buffer: object) -> None:
        """Push a buffer downstream to the linked sink pad."""
        if self.direction != PadDirection.SRC:
            raise ValueError("push is only valid on src pads")
        if not self.peer:
            raise ValueError("pad is not linked")
        return self.peer.element.on_buffer(self.peer, buffer)
