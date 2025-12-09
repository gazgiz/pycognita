"""# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial"""
from __future__ import annotations

"""Base class for narrator elements that describe content."""

from .caps import Caps
from .element import Element, CapsNegotiationError
from .pad import PadDirection

TEXT_CAPS = Caps(
    media_type="text/plain",
    name="plain-text",
    params={
        "description": "Plain text content.",
        "extensions": ("txt",),
        "uri": "urn:cognita:caps:plain-text",
        "broader": ("urn:cognita:category:content",),
    },
)

NARRATION_CAPS = Caps(
    media_type="text/plain",
    name="plain-text",
    params={
        "description": "Machine-generated text description.",
        "extensions": ("txt",),
        "uri": "urn:cognita:caps:text:machine-narrated",
        "broader": ("urn:cognita:caps:plain-text",),
    },
)


class Narrator(Element):
    """Base element that consumes content and produces a text description.
    
    This class serves as a foundation for all "Narrator" elements.
    It enforces strict Caps negotiation: if upstream Caps are incompatible,
    it raises CapsNegotiationError immediately.
    """

    def __init__(self) -> None:
        super().__init__()
        self._caps: Caps | None = None
        self._output_caps = NARRATION_CAPS

    def process(self) -> None:
        return

    def handle_event(self, pad, event: str, payload: object | None = None) -> None:
        """Handle control events, enforcing strict Caps compatibility."""
        if event == "caps":
            if not isinstance(payload, Caps):
                raise TypeError("Narrator caps event requires Caps payload")
            
            # STRICT CHECK: Can we process these caps?
            # Passing None for payload because we only check Type compatibility here.
            if not self._can_process(payload, None):
                raise CapsNegotiationError(f"{self.__class__.__name__} cannot handle caps: {payload}")

            # Store upstream caps
            pad.caps = payload
            self._caps = payload
            
            # Forwarding caps downstream is problematic if we change the type (e.g. image -> text).
            # We DONT forward the input caps here because we are a converter.
            # We will emit our OWN output caps when we produce data.
            return
        return super().handle_event(pad, event, payload)

    def on_buffer(self, pad, payload: object) -> None:
        """Handle incoming buffer.
        
        Assumes Caps have been negotiated successfully.
        """
        caps = self._caps or getattr(pad, "caps", None)
        
        # Runtime check: even if caps matched, does the payload have what we need?
        # (e.g. URI exists)
        if not self._can_process(caps, payload):
             # This is now a runtime error, or we silently drop. 
             # For robustness, we'll log/drop, but strictly NO passthrough of raw data.
             return

        description = self._narrate(payload, caps)
        if description:
            self._announce_output_caps(caps)
            self._push_downstream(description)

    def _can_process(self, caps: Caps | None, payload: object | None) -> bool:
        """Check if this narrator can process the given caps/payload.
        
        Subclasses must override this.
        If payload is None, this method should return True if the Caps *might* be supported.
        """
        raise NotImplementedError

    def _narrate(self, payload: object, caps: Caps | None) -> str | None:
        """Generate a description for the payload."""
        raise NotImplementedError

    def _push_downstream(self, payload: object) -> None:
        for pad in self.pads:
            if pad.direction == PadDirection.SRC and pad.peer:
                pad.peer.element.on_buffer(pad.peer, payload)

    def _announce_output_caps(self, input_caps: Caps | None = None) -> None:
        final_caps = self._output_caps
        
        if input_caps:
            # Propagate Identity from upstream
            new_params = {}
            # Check safely for params existence (backward compat)
            p = getattr(input_caps, "params", {})
            
            if p.get("fingerprint"):
                new_params["fingerprint"] = p["fingerprint"]
                
            if new_params:
                final_caps = final_caps.merge_params(new_params)
        
        self._caps = final_caps
        for pad in self.pads:
            if pad.direction == PadDirection.SRC:
                pad.set_caps(final_caps, propagate=True)
