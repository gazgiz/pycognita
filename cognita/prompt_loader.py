# SPDX-License-Identifier: GPL-3.0-or-later OR LicenseRef-Commercial
"""Utility to load prompt templates from the cognita.prompts package."""

import importlib.resources

def load_prompt(filename: str) -> str:
    """Load a prompt file from the cognita.prompts package.
    
    Args:
        filename: The name of the file to load (e.g., 'triple_extractor_system.txt').
        
    Returns:
        The content of the file as a string.
    """
    try:
        # Use importlib.resources to read the file from the package
        return importlib.resources.files("cognita.prompts").joinpath(filename).read_text(encoding="utf-8")
    except Exception as e:
        # In case of error (e.g., file not found), return empty or raise
        # For robustness, we log or raise. Here we'll raise to fail fast during dev.
        raise FileNotFoundError(f"Could not load prompt file '{filename}': {e}") from e
