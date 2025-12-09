"""# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial"""
from __future__ import annotations

"""File type detection helpers with header heuristics and Ollama fallback.

Key pieces:
  - HeaderDetector: small predicate paired with a resulting Caps.
  - HeaderAnalyzer: runs detectors sequentially to find the first match.
  - summarize_caps: emits a compact JSON summary for CLI output.
"""

import hashlib
import binascii
import os
import re
from email.parser import BytesHeaderParser
from dataclasses import dataclass
from typing import Callable, List, Sequence, Any

from .caps import Caps


@dataclass(frozen=True)
class HeaderDetector:
    """Mapping of a detection function to its resulting Caps.

    Each detector encapsulates a single heuristic check (e.g., "does it start with %PDF-?")
    and the corresponding Caps object to return if the check passes.
    """

    name: str
    detector: Callable[[bytes], bool]
    caps: Caps


DOCUMENT_CAPS = Caps(
    media_type="document",
    name="document",
    params={
        "description": "Document-like content (pdf, docx, txt, html).",
        "extensions": ("pdf", "docx", "pptx", "xlsx", "txt", "md", "html"),
        "uri": "urn:cognita:caps:document",
        "broader": ("urn:cognita:category:content",),
    },
)

IMAGE_CAPS = Caps(
    media_type="image",
    name="image-photo",
    params={
        "description": "Still image or photo (png, jpeg, gif, webp).",
        "extensions": ("png", "jpg", "jpeg", "gif", "webp"),
        "uri": "urn:cognita:caps:image-photo",
        "broader": ("urn:cognita:category:content",),
    },
)

VIDEO_CAPS = Caps(
    media_type="video",
    name="video",
    params={
        "description": "Video container (mp4/mov).",
        "extensions": ("mp4", "m4v", "mov"),
        "uri": "urn:cognita:caps:video",
        "broader": ("urn:cognita:category:content",),
    },
)

MBOX_CAPS = Caps(
    media_type="application/mbox",
    name="application-mbox",
    params={
        "description": "Email archive (mbox).",
        "extensions": ("mbox",),
        "uri": "urn:cognita:caps:application-mbox",
        "broader": ("urn:cognita:category:content",),
    },
)

EML_CAPS = Caps(
    media_type="message/rfc822",
    name="message-rfc822",
    params={
        "description": "Email message (eml/rfc822).",
        "extensions": ("eml",),
        "uri": "urn:cognita:caps:message-rfc822",
        "broader": ("urn:cognita:category:content",),
    },
)

CALENDAR_CAPS = Caps(
    media_type="calendar",
    name="calendar",
    params={
        "description": "Calendar data (ICS/vCalendar).",
        "extensions": ("ics",),
        "uri": "urn:cognita:caps:calendar",
        "broader": ("urn:cognita:category:content",),
    },
)

BINARY_CAPS = Caps(
    media_type="binary",
    name="binary-file",
    params={
        "description": "Executable or opaque binary data (zip, elf, etc).",
        "extensions": None,
        "uri": "urn:cognita:caps:binary",
        "broader": ("urn:cognita:category:content",),
    },
)


def _decode_lower(data: bytes, max_len: int = 2048) -> str:
    """Decode bytes to lowercase text for heuristic checks."""
    return preview_text(data, max_len).lower()


def _is_calendar(data: bytes) -> bool:
    """Detect iCalendar content (ICS)."""
    text = _decode_lower(data)
    return "begin:vcalendar" in text and "end:vcalendar" in text


def _is_mbox(data: bytes) -> bool:
    """Detect mbox format (From line with timestamp).

    Mbox files typically start with a "From " line that acts as a separator.
    We check for this specific pattern to distinguish mbox from regular text.
    """
    # Check for "From " at the start
    if not data.startswith(b"From "):
        return False
    
    # Decode first line to check pattern
    try:
        first_line = data.split(b"\n", 1)[0].decode("utf-8")
    except UnicodeDecodeError:
        return False

    # Regex for mbox "From " line: From <email> <timestamp>
    # Example: From MAILER-DAEMON Fri Jul  8 12:08:34 2011
    # We'll use a slightly relaxed regex to catch variations
    # "From " + non-whitespace + whitespace + ... + digit
    pattern = r"^From \S+ .+\d{4}$"
    return bool(re.match(pattern, first_line))


def _is_eml(data: bytes) -> bool:
    """Detect EML/RFC822 format via headers.

    We look for standard email headers like 'Subject:' and 'From:' in the first block.
    """
    header = _decode_lower(data)
    # EML usually has Subject: and From: headers
    has_subject = "subject:" in header
    has_from = "from:" in header
    return has_subject and has_from


def _is_pdf(data: bytes) -> bool:
    """Detect PDF magic bytes (%PDF-)."""
    return data.startswith(b"%PDF-")


def _is_png(data: bytes) -> bool:
    """Detect PNG signature."""
    return data.startswith(b"\x89PNG\r\n\x1a\n")


def _is_jpeg(data: bytes) -> bool:
    """Detect JPEG signature (FF D8 FF)."""
    return data.startswith(b"\xff\xd8\xff")


def _is_gif(data: bytes) -> bool:
    """Detect GIF signature (GIF87a or GIF89a)."""
    return data.startswith(b"GIF87a") or data.startswith(b"GIF89a")


def _is_mp4(data: bytes) -> bool:
    """Detect MP4/ISOBMFF container by `ftyp` box."""
    return len(data) >= 12 and data[4:8] == b"ftyp"


def _is_ooxml_zip(data: bytes) -> bool:
    """Detect Office Open XML archives (docx, pptx, xlsx).

    These are ZIP files containing specific XML structures.
    """
    if not data.startswith(b"PK\x03\x04"):
        return False
    return any(marker in data for marker in (b"[Content_Types].xml", b"word/", b"ppt/", b"xl/"))


def _is_zip(data: bytes) -> bool:
    """Detect generic ZIP archives."""
    return data.startswith(b"PK\x03\x04")


def _is_elf(data: bytes) -> bool:
    """Detect ELF binaries (Linux executables)."""
    return data.startswith(b"\x7fELF")


def _is_text_document(data: bytes) -> bool:
    """Detect text-heavy files while excluding calendar markers.

    Heuristic:
    1. Check if a high percentage of bytes are printable ASCII/whitespace.
    2. Ensure it's not a calendar file (which is also text but handled separately).
    """
    sample = data[:2048]
    if not sample:
        return False

    printable = sum(1 for byte in sample if 32 <= byte <= 126 or byte in (9, 10, 13))
    density = printable / len(sample)
    if density < 0.85:
        return False

    lower = _decode_lower(sample)
    calendar = "begin:vcalendar" in lower
    return not calendar


DEFAULT_DETECTORS: List[HeaderDetector] = [
    # Order matters: check specific formats before generic ones (like zip or text).
    HeaderDetector("calendar", _is_calendar, CALENDAR_CAPS),
    HeaderDetector("mbox", _is_mbox, MBOX_CAPS),
    HeaderDetector("eml", _is_eml, EML_CAPS),
    HeaderDetector("pdf", _is_pdf, DOCUMENT_CAPS),
    HeaderDetector("ooxml-zip", _is_ooxml_zip, DOCUMENT_CAPS),
    HeaderDetector("mp4", _is_mp4, VIDEO_CAPS),
    HeaderDetector("png", _is_png, IMAGE_CAPS),
    HeaderDetector("jpeg", _is_jpeg, IMAGE_CAPS),
    HeaderDetector("gif", _is_gif, IMAGE_CAPS),
    HeaderDetector("zip", _is_zip, BINARY_CAPS),
    HeaderDetector("elf", _is_elf, BINARY_CAPS),
    HeaderDetector("text-document", _is_text_document, DOCUMENT_CAPS),
]


def header_sample_to_hex(data: bytes, max_len: int = 64) -> str:
    """Hex-encode the first bytes of a payload for logging/LLM prompts."""
    return binascii.hexlify(data[:max_len]).decode("ascii")


def preview_text(data: bytes, max_len: int = 400) -> str:
    """Decode a short preview of bytes with UTF-8 first, latin-1 fallback."""
    snippet = data[:max_len]
    try:
        return snippet.decode("utf-8")
    except UnicodeDecodeError:
        return snippet.decode("latin-1", errors="ignore")


class HeaderAnalyzer:
    """Sequentially executes detectors to identify a Caps match."""

    def __init__(self, detectors: Sequence[HeaderDetector] | None = None):
        self.detectors = list(detectors or DEFAULT_DETECTORS)

    def detect(self, data: bytes) -> Caps | None:
        for detector in self.detectors:
            try:
                if detector.detector(data):
                    return detector.caps
            except Exception:  # pragma: no cover - defensive
                continue
        return None


def compute_identity(uri: str, caps: Caps) -> dict[str, Any]:
    """Compute identification params for the given file and caps.

    - For mail (EML), attempts to extract Message-ID.
    - For others, computes SHA-256 fingerprint of the file.
    """
    params = {}
    
    path = uri[len("file://") :] if uri.startswith("file://") else uri
    
    # Only verify existence if we need to read it (which we do for both cases)
    if not os.path.isfile(path):
        return params

    # Strategy 1: Mail Message-ID (Single EML only)
    if caps.name == "message-rfc822":
        try:
            with open(path, "rb") as f:
                # Read enough for headers
                head_sample = f.read(32_768)
                parser = BytesHeaderParser()
                msg = parser.parsebytes(head_sample)
                msg_id = msg.get("Message-ID")
                if msg_id:
                     params["fingerprint"] = msg_id.strip()
                     return params
        except Exception:
            pass # Fallback to fingerprint

    # Strategy 2: Full SHA-256 Fingerprint (Fallback + MBOX)
    # MBOX (application-mbox) naturally falls through here.

    # Strategy 2: Full SHA-256 Fingerprint
    try:
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(65_536) # 64KB chunks
                if not chunk:
                    break
                sha256.update(chunk)
        params["fingerprint"] = sha256.hexdigest()
    except OSError:
        pass
        
    return params


class TypeFinderError(RuntimeError):
    """Raised when type inference fails or prerequisites are missing."""
