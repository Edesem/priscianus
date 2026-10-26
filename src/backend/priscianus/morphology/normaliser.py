"""Normalise Latin surface forms into lookup keys."""

import unicodedata

_LIGATURES = str.maketrans({"æ": "ae", "œ": "oe"})
_CONSONANTAL = str.maketrans({"v": "u", "j": "i"})


def key_loose(form: str) -> str:
    """Lowercase key with length marks removed and u/v, i/j folded.

    Spelling variants such as caelum/coelum and enclitics such as -que are
    left distinct; only the ae and oe ligatures are expanded.
    """
    decomposed = unicodedata.normalize("NFD", form.strip().casefold())
    bare = "".join(c for c in decomposed if not unicodedata.combining(c))
    return bare.translate(_LIGATURES).translate(_CONSONANTAL)
