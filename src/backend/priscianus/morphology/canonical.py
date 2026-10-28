"""Canonical form of UD features, so gold data, claims and index analyses compare equal.

The UD treebanks encode the same grammar differently (see ADR-003, Decision 2).
`canonicalise` applies one set of rules to every source before any comparison.
"""

from collections.abc import Mapping

_PARTICIPLE_TENSE = {"Imp": "Pres", "Perf": "Past", "Prosp": "Fut"}


def canonicalise(features: Mapping[str, str]) -> dict[str, str]:
    """Return `features` in canonical form.

    A multi-valued feature ("Gender=Fem,Masc") stays one entry, with its members sorted.
    """
    result = {name: _sorted_members(value) for name, value in features.items()}

    if result.get("VerbForm") == "Part" and "Aspect" in result:
        result.setdefault("Tense", _PARTICIPLE_TENSE.get(result["Aspect"], result["Aspect"]))
        del result["Aspect"]
    if _is_gerundive(result):
        result["VerbForm"] = "Gdv"
    if result.get("VerbForm") == "Gdv":
        result.pop("Tense", None)
        result.pop("Voice", None)

    tense = result.get("Tense")
    if not (tense == "Past" or (tense == "Fut" and result.get("Aspect") == "Perf")):
        result.pop("Aspect", None)

    if "Degree" in result:
        degrees = [
            "Sup" if member == "Abs" else member
            for member in result["Degree"].split(",")
            if member != "Pos"
        ]
        if degrees:
            result["Degree"] = ",".join(degrees)
        else:
            del result["Degree"]
    return result


def relax(
    features: Mapping[str, str], *, noun: bool, deponent: bool, pronoun: bool = False
) -> dict[str, str]:
    """Drop what a comparison with the index cannot check (ADR-002, ADR-003).

    Index noun forms carry no gender, since it belongs to the lemma. The index tags
    every form of a deponent Voice=Act, where other sources say passive. Nor do index
    pronoun forms carry person, which the gold marks (*ego* 1, *tu* 2, *is* 3).
    """
    dropped = {"Gender"} if noun else set()
    if pronoun:
        dropped.add("Person")
    if deponent:
        dropped.add("Voice")
    return {name: value for name, value in features.items() if name not in dropped}


def _is_gerundive(features: Mapping[str, str]) -> bool:
    return (
        features.get("VerbForm") == "Part"
        and features.get("Tense") == "Fut"
        and features.get("Voice") == "Pass"
    )


def _sorted_members(value: str) -> str:
    return ",".join(sorted(value.split(",")))
