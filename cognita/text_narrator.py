"""# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial"""
from __future__ import annotations

"""Narrator for plain text files."""

import os

from .caps import Caps
from .narrator import Narrator
from .ollama import OllamaClient, OllamaError


class TextNarrator(Narrator):
    """Reads a plain text file and uses Ollama to summarize/extract info.
    
    This narrator operates on content identified as 'plain-text' or 'document'.
    It supports both capped (upstream identified) and uncapped (URI-only) modes.
    """

    def __init__(self, ollama_client: OllamaClient | None = None):
        super().__init__()
        # Use provided client or default to a text-capable model.
        # While ImageNarrator defaults to vision model, here we can use same or standard llama3.
        # But for consistency with user env, we'll keep qwen2.5vl:3b as default or let caller specify.
        # If the user has qwen2.5vl:3b, it handles text fine too.
        self.ollama_client = ollama_client or OllamaClient(model="qwen2.5vl:3b")

    def _can_process(self, caps: Caps | None, payload: object) -> bool:
        # 1. Capped mode
        if isinstance(caps, Caps):
            return caps.name in ("plain-text", "document")

        # 2. Uncapped mode
        if isinstance(payload, dict) and "uri" in payload:
            uri = payload["uri"]
            # Basic extension check for text files
            # This list can be expanded or we could peek at content if needed.
            return uri.lower().endswith((".txt", ".md", ".csv", ".json", ".log"))
        
        return False

    def _narrate(self, payload: object, caps: Caps | None) -> str | None:
        """Read the text file and generate a summary."""
        if not isinstance(payload, dict):
            return None
            
        uri = payload.get("uri")
        data = payload.get("data")
        
        text_content = ""
        
        # Try to use pre-buffered data if valid text
        if data:
            try:
                text_content = data.decode("utf-8")
            except Exception:
                # If binary data found in 'data', we might ignore it or try to re-read file
                pass
        
        # If no data or decoding failed, try reading from URI
        if not text_content and uri:
             path = self._uri_to_path(uri)
             if os.path.isfile(path):
                 try:
                     with open(path, "r", encoding="utf-8", errors="replace") as f:
                         text_content = f.read()
                 except Exception:
                     pass

        if not text_content:
            return "Empty or unreadable text content."

        if not self.ollama_client:
             # Fallback if no LLM
             return f"Text content ({len(text_content)} chars): {text_content[:200]}..."

        prompt = (
            "Analyze this text for Knowledge Graph extraction.\n"
            "1. Summarize the main topic.\n"
            "2. Extract key entities and their relationships.\n"
            "Output strictly as a list of atomic statements in this format:\n"
            "- [Entity A] [relationship] [Entity B]\n"
            "- [Entity] is [Attribute]\n"
            "Do NOT write paragraphs. List separate facts."
        )
        
        try:
            # We limit text content to avoid context window issues if very large
            # 100kb is a safe conservative limit for now, or let Ollama truncate.
            safe_content = text_content[:50000] 
            return self.ollama_client._request(f"{prompt}\n\nText:\n{safe_content}")
        except OllamaError as error:
             return f"[ollama error] {error}"

    @staticmethod
    def _uri_to_path(uri: str) -> str:
        if uri.startswith("file://"):
            return uri[len("file://") :]
        return uri
