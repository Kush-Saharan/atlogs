"""Terminology normalisation (M.3): map abbreviations/synonyms to canonical terms. Pure."""
from __future__ import annotations
import re


def key(term: str) -> str:
    """Lowercase, punctuation stripped, whitespace collapsed."""
    return " ".join(re.sub(r"[^\w\s]", " ", term.lower()).split())


def normalise(text: str, table: dict[str, str]) -> str:
    """Replace each token found in `table` (keys already in `key()` form) with its
    canonical term. Unknown tokens pass through unchanged (original case kept).
    shortcut: single-word terms only, add phrase matching when M.4 needs it."""
    return re.sub(r"\w+", lambda m: table.get(key(m.group()), m.group()), text)
