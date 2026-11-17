"""Line up the model's claims with the words the student typed (ADR-005, Decision 2).

No model is involved. A word without a claim is listed as `not_explained`, never dropped.
"""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from priscianus.morphology.normaliser import key_loose
from priscianus.pipeline.verify import VerifiedClaim

NOT_EXPLAINED = "not_explained"
ENCLITICS = ("que", "ne", "ve")

_WORD = re.compile(r"[^\W\d_]+")


@dataclass(frozen=True)
class WordResult:
    """One typed word, its claim if it got one, and a note (`enclitic -que`, `not_explained`)."""

    token: str
    claim: VerifiedClaim | None
    note: str | None


def tokenise(text: str) -> list[str]:
    """The words of `text`, as typed. A word is a run of letters (macrons allowed)."""
    return _WORD.findall(unicodedata.normalize("NFC", text))


def line_up(tokens: Sequence[str], claims: Sequence[VerifiedClaim]) -> tuple[list[WordResult], int]:
    """One `WordResult` per token, in order, and the number of claims that match no token.

    A claim matches a token if their loose keys are equal, or if the token is the claim's form
    plus an enclitic. Each claim is used once, so a repeated word takes its claims in order.
    """
    unused = list(claims)
    words = []
    for token in tokens:
        found = _take_match(token, unused)
        if found is None:
            words.append(WordResult(token, None, NOT_EXPLAINED))
        else:
            words.append(WordResult(token, found[0], found[1]))
    return words, len(unused)


def _take_match(token: str, unused: list[VerifiedClaim]) -> tuple[VerifiedClaim, str | None] | None:
    key = key_loose(token)
    for verified in unused:
        form = key_loose(verified.claim.form)
        if form == key:
            unused.remove(verified)
            return verified, None
        for enclitic in ENCLITICS:
            if key == form + enclitic:
                unused.remove(verified)
                return verified, f"enclitic -{enclitic}"
    return None
