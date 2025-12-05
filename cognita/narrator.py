"""# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial"""
from __future__ import annotations

"""Base class for narrator elements that describe content."""

from .caps import Caps
from .element import Element
from .pad import PadDirection

TEXT_CAPS = Caps(
    media_type="text/plain",
    name="plain-text",
    description="Plain text content.",
    extensions=("txt",),
    uri="urn:cognita:caps:plain-text",
    broader=("urn:cognita:category:content",),
)

NARRATION_CAPS = Caps(
    media_type="text/plain",
    name="plain-text",
    description="Machine-generated text description.",
    extensions=("txt",),
    uri="urn:cognita:caps:text:machine-narrated",
    broader=("urn:cognita:caps:plain-text",),
)


class Narrator(Element):
    """Base element that consumes content and produces a text description.
    
    This class serves as a foundation for all "Narrator" elements (e.g., ImageNarrator,
    MailboxNarrator). Its primary responsibility is to:
    1. Receive an incoming buffer (payload).
    2. Check if it can process that payload (via `_can_process`).
    3. If yes, generate a text description (via `_narrate`).
    4. Wrap the description in a new payload with NARRATION_CAPS and push it downstream.
    5. If no, pass the original payload downstream unchanged (passthrough).
    """

    def __init__(self) -> None:
        super().__init__()
        self._caps: Caps | None = None
        self._output_caps = NARRATION_CAPS

    def process(self) -> None:
        # No-op: work is reactive in on_buffer.
        # Narrators are filters, not sources, so they don't initiate processing loop.
        return

    def handle_event(self, pad, event: str, payload: object | None = None) -> None:
        """Handle control events, primarily Caps negotiation."""
        if event == "caps":
            if not isinstance(payload, Caps):
                raise TypeError("Narrator caps event requires Caps payload")
            
            # Store upstream caps
            pad.caps = payload
            self._caps = payload
            
            # Forward caps downstream to peers.
            # Note: If this narrator produces text, it will later announce TEXT_CAPS
            # when it actually produces data. But we forward the original caps here
            # in case we end up in passthrough mode.
            for peer in (p for p in self.pads if p.direction == PadDirection.SRC and p.peer):
                peer.peer.caps = payload
                peer.peer.element.handle_event(peer.peer, event, payload)
            return
        return super().handle_event(pad, event, payload)

    def on_buffer(self, pad, payload: object) -> None:
        """Handle incoming buffer. Subclasses should override _narrate.
        
        Logic:
        - Retrieve upstream caps (from event or pad).
        - Check `_can_process(caps, payload)`:
            - If False: Treat as unknown content, push original payload downstream.
            - If True: Call `_narrate(payload, caps)`.
        - If `_narrate` returns a string:
            - Announce TEXT_CAPS (since we are changing the data type).
            - Push the description string downstream.
        """
        caps = self._caps or getattr(pad, "caps", None)
        
        if not self._can_process(caps, payload):
             self._push_downstream(payload)
             return

        description = self._narrate(payload, caps)
        if description:
            self._announce_output_caps()
            self._push_downstream(description)
        else:
            # If narration failed or returned None, we currently do nothing.
            # Alternatively, we could log a warning or push the original payload.
            pass

    def _can_process(self, caps: Caps | None, payload: object) -> bool:
        """Check if this narrator can process the given caps/payload.
        
        Subclasses must override this to define what they accept.
        """
        raise NotImplementedError

    def _narrate(self, payload: object, caps: Caps | None) -> str | None:
        """Generate a description for the payload.
        
        Subclasses must override this.
        """
        raise NotImplementedError

    def _push_downstream(self, payload: object) -> None:
        for pad in self.pads:
            if pad.direction == PadDirection.SRC and pad.peer:
                pad.peer.element.on_buffer(pad.peer, payload)

    def _announce_output_caps(self) -> None:
        self._caps = self._output_caps
        for pad in self.pads:
            if pad.direction == PadDirection.SRC:
                pad.set_caps(self._output_caps, propagate=True)
