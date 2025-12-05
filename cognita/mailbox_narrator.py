"""# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial"""
from __future__ import annotations

"""Narrator for mailbox files (mbox)."""

import mailbox
import os
from typing import Any

from .caps import Caps
from .narrator import Narrator
from .type_finder import _is_eml, _is_mbox


class MailboxNarrator(Narrator):
    """Reads a mailbox (mbox) and narrates its contents (sender, subject, date).
    
    This narrator supports two modes of operation:
    1. Capped: Upstream element (e.g., TypeFinder) has already identified the content as 'mail'.
    2. Uncapped (URI-only): Upstream (e.g., DiscreteDataSource) provided a URI but no caps.
       In this case, we perform our own lightweight detection to verify it's a mailbox.
    """

    def _can_process(self, caps: Caps | None, payload: object) -> bool:
        # 1. If caps are present, we trust them.
        if isinstance(caps, Caps):
             return caps.name == "mail"

        # 2. If no caps, we need a URI to access the file directly.
        if not isinstance(payload, dict) or "uri" not in payload:
            return False
        
        uri = payload["uri"]
        path = self._uri_to_path(uri)
        
        if not os.path.isfile(path):
            return False
            
        # 3. Read a small header sample to verify type before claiming it.
        # This prevents us from trying to parse random files as mbox.
        try:
            with open(path, "rb") as f:
                header = f.read(2048)
                return _is_mbox(header) or _is_eml(header)
        except Exception:
            return False

    def _narrate(self, payload: object, caps: Caps | None) -> str | None:
        """Read the mailbox file and generate a summary."""
        if not isinstance(payload, dict):
            return None
        
        uri = payload.get("uri")
        if not uri:
            return None

        path = self._uri_to_path(uri)
        try:
            # Use Python's built-in mailbox module to parse the file.
            mbox = mailbox.mbox(path)
            summary = [f"Mailbox: {os.path.basename(path)} containing {len(mbox)} messages.\n"]
            
            # Iterate through messages and extract key metadata.
            for i, message in enumerate(mbox):
                subject = message["subject"] or "(No Subject)"
                sender = message["from"] or "(Unknown Sender)"
                date = message["date"] or "(Unknown Date)"
                summary.append(f"{i+1}. [{date}] From: {sender} | Subject: {subject}")
                
                # Limit to first 50 messages to avoid huge output for now.
                # In a real system, we might want to stream this or paginate.
                if i >= 49:
                    summary.append(f"... and {len(mbox) - 50} more messages.")
                    break
            
            return "\n".join(summary)
        except Exception as e:
            return f"Failed to read mailbox: {e}"

    @staticmethod
    def _uri_to_path(uri: str) -> str:
        if uri.startswith("file://"):
            return uri[len("file://") :]
        return uri
