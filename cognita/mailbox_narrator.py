# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial

from __future__ import annotations

import mailbox
import os

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
        # 1. If caps are present, we trust them (usually).
        if (
            isinstance(caps, Caps)
            and caps.name in ("application-mbox", "message-rfc822")
            and (
                payload is None
                or isinstance(payload, bytes)
                or (isinstance(payload, dict) and "uri" in payload)
            )
        ):
            return True

        # 2. If no caps, we need a URI to access the file directly.
        if not isinstance(payload, dict) or "uri" not in payload:
            return False

        uri = payload["uri"]
        path = self._uri_to_path(uri)

        if not os.path.isfile(path):
            return False

        # 3. Read a small header sample to verify type before claiming it.
        try:
            with open(path, "rb") as f:
                header = f.read(2048)
                return _is_mbox(header) or _is_eml(header)
        except Exception:
            return False

    def _narrate(self, payload: object, caps: Caps | None) -> str | None:
        """Read the mailbox file OR single message content and generate a summary."""
        import email
        from email.policy import default

        # Case A: Direct Bytes (Single Message from MboxParser)
        if isinstance(payload, bytes):
            try:
                # Treat as single email message
                msg = email.message_from_bytes(payload, policy=default)
                subject = msg.get("subject", "(No Subject)")
                sender = msg.get("from", "(Unknown Sender)")
                date = msg.get("date", "(Unknown Date)")
                return f"Message: [{date}] From: {sender} | Subject: {subject}"
            except Exception as e:
                return f"Failed to parse email message: {e}"

        # Case B: File URI (Whole Mbox File)
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
                summary.append(f"{i + 1}. [{date}] From: {sender} | Subject: {subject}")

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
