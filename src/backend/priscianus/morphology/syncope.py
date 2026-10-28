"""Syncopated perfects: *nuntiārunt* for *nuntiāvērunt*, *custōdīstis* for *custōdīvistis*."""

import unicodedata

# What follows the dropped letters: -st- (-istī, -istis), -ss- (-isse, -issem), -run- (-ērunt),
# -rin- (-erint) and -rit- (-erit). Other endings (-vit, -vī, -vērat) are not syncopated.
_ENDINGS = ("st", "ss", "run", "rin", "rit")


def syncopate(form: str) -> str | None:
    """The syncopated spelling of a perfect-stem form with -āv- or -īv-, or None.

    -āvi- and -āve- lose the v and the vowel after it, as does -īvi-; -īve- loses only the v
    (*audīvērunt* → *audiērunt*). Length marks on the letters that stay are kept.
    """
    units = _units(form)
    letters = [unit[0].casefold() for unit in units]
    for i in range(1, len(letters) - 2):
        before, after = letters[i - 1], letters[i + 1]
        if letters[i] != "v" or before not in "ai" or after not in "ie":
            continue
        if not "".join(letters[i + 2 :]).startswith(_ENDINGS):
            continue
        if before == "i" and after == "e":
            kept = units[: i - 1] + [units[i - 1][0]] + units[i + 1 :]  # ī shortens before ē
        else:
            kept = units[:i] + units[i + 2 :]
        return unicodedata.normalize("NFC", "".join(kept))
    return None


def _units(form: str) -> list[str]:
    """Split into letters, each with the length marks attached to it."""
    units: list[str] = []
    for char in unicodedata.normalize("NFD", form):
        if unicodedata.combining(char) and units:
            units[-1] += char
        else:
            units.append(char)
    return units
