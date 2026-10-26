"""Normalise Latin surface forms into lookup keys."""

import unicodedata

_MACRON = "̄"
_LIGATURES = str.maketrans({"æ": "ae", "œ": "oe"})
_CONSONANTAL = str.maketrans({"v": "u", "j": "i"})


def _fold(form: str, keep: str) -> str:
    decomposed = unicodedata.normalize("NFD", form.strip().casefold())
    kept = "".join(c for c in decomposed if not unicodedata.combining(c) or c == keep)
    folded = kept.translate(_LIGATURES).translate(_CONSONANTAL)
    return unicodedata.normalize("NFC", folded)


def key_loose(form: str) -> str:
    """Lowercase key with length marks removed and u/v, i/j folded.

    Spelling variants such as caelum/coelum and enclitics such as -que are
    left distinct; only the ae and oe ligatures are expanded.
    """
    return _fold(form, keep="")


def key_macron(form: str) -> str:
    """Like `key_loose` but keeps macrons, for claims that state vowel length."""
    return _fold(form, keep=_MACRON)
