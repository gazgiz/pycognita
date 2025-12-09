# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial
from __future__ import annotations

import mailbox
import os
import sys
from typing import Any

from .caps import Caps
from .element import Element
from .pad import PadDirection, Pad

class MboxParser(Element):
    """Parses Mbox files and splits them into individual message buffers.
    
    Enriches output caps with:
    - count: Total number of messages.
    """
    
    
    def __init__(self) -> None:
        super().__init__()

    def process(self) -> None:
        pass

    def on_buffer(self, pad: Pad, buffer: object) -> None:
        if pad.direction != PadDirection.SINK:
            return

        # 1. Check Caps
        if not pad.caps or pad.caps.name != "application-mbox":
            # Just pass through or error? 
            # User requirement: "operate ONLY if source caps is application/mbox"
            print(f"[warning] MboxParser received non-mbox caps: {pad.caps}", file=sys.stderr)
            return

        # 2. Parse Payload (Expect uri in dict)
        if not isinstance(buffer, dict) or "uri" not in buffer:
            return

        uri = buffer["uri"]
        path = uri[len("file://"):] if uri.startswith("file://") else uri
        
        if not os.path.exists(path):
            return

        try:
            mbox = mailbox.mbox(path)
            messages = []
            fingerprints = []
            
            # Read all messages to gather metadata first
            # (Note: for huge mboxes this might be memory intensive, but required to populate caps first)
            for msg in mbox:
                messages.append(msg)
            
            # 3. Construct Output Caps
            out_params = pad.caps.params.copy() if pad.caps.params else {}
            out_params["count"] = len(messages)
            
            # "Output caps is similarly application/mbox"
            output_caps = Caps(
                media_type="application/mbox",
                name="application-mbox",
                params=out_params
            )
            
            # Set caps on src pads
            self._set_src_caps(output_caps)
            
            # 4. Push Messages
            for msg in messages:
                # Push the message object (or bytes? Element protocol is usually transparent)
                # Let's push the raw message bytes/string representation as a standard payload
                # or verify if we should wrap it. 
                # "deliver data in unit of one message".
                # To be most compatible with downstream parsers (like EmlNarrator), 
                # usually raw bytes of the message is best.
                payload = msg.as_bytes()
                self._push_src(payload)
                    
        except Exception as e:
            print(f"[error] MboxParser failed: {e}", file=sys.stderr)
            
    def _set_src_caps(self, caps: Caps) -> None:
        for pad in self.pads:
            if pad.direction == PadDirection.SRC:
                pad.set_caps(caps, propagate=True)

    def _push_src(self, payload: Any) -> None:
        for pad in self.pads:
            if pad.direction == PadDirection.SRC and pad.peer:
                pad.peer.element.on_buffer(pad.peer, payload)
