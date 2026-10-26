"""Normalise Latin surface forms into lookup keys."""

import unicodedata


def key_loose(form: str) -> str:
    """Lowercase key with all length marks and other diacritics removed."""
    decomposed = unicodedata.normalize("NFD", form.strip().casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))
