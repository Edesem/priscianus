"""Record Whitaker's Words analyses of a fixed word list as a JSON fixture.

Needs PyWORDS (https://github.com/sjgallagher2/PyWORDS), which is not a backend
dependency. Install it in a throwaway virtualenv and run this script with that
interpreter:

    python -I generate_whitakers_spot_check.py [OUTPUT]

The output (default: src/data/spot_check/whitakers.json) keeps Whitaker's own
inflection codes; priscianus.morphology.whitakers maps them to UD at compare time.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pywords import definitions, lookup

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "spot_check" / "whitakers.json"

# Forms chosen to cover each declension and conjugation, adjectives, pronouns,
# irregular and deponent verbs, and the non-finite verb forms.
WORDS = [
    "puellae",
    "rosarum",
    "aquam",
    "poeta",
    "dominus",
    "domini",
    "servo",
    "bellum",
    "bella",
    "pueri",
    "filiorum",
    "deo",
    "regum",
    "regis",
    "regi",
    "rege",
    "civitatem",
    "nomina",
    "corporis",
    "patris",
    "nomine",
    "mare",
    "maria",
    "urbium",
    "manus",
    "manui",
    "exercitum",
    "fructus",
    "cornua",
    "diei",
    "rem",
    "rebus",
    "fidem",
    "speciem",
    "bonus",
    "bonae",
    "bonorum",
    "bono",
    "magnam",
    "magna",
    "melior",
    "meliorem",
    "optimus",
    "fortis",
    "fortem",
    "fortibus",
    "omnia",
    "omnium",
    "acris",
    "pulchriorem",
    "ingentes",
    "felix",
    "felicis",
    "ego",
    "mihi",
    "nos",
    "tibi",
    "eius",
    "hic",
    "illa",
    "quod",
    "eum",
    "illi",
    "hoc",
    "quem",
    "sibi",
    "amo",
    "amas",
    "amat",
    "amamus",
    "amabat",
    "amavit",
    "amabo",
    "amaret",
    "amare",
    "amari",
    "amatus",
    "amantem",
    "amandi",
    "amatum",
    "ama",
    "laudaverunt",
    "laudavisse",
    "laudabimus",
    "laudemus",
    "monet",
    "monebant",
    "monuit",
    "monere",
    "monete",
    "monitus",
    "regit",
    "regunt",
    "regebat",
    "rexit",
    "reget",
    "regere",
    "regamus",
    "regitur",
    "capit",
    "capiunt",
    "capiebat",
    "cepit",
    "capere",
    "capiet",
    "audit",
    "audiunt",
    "audiebat",
    "audivit",
    "audire",
    "audiat",
    "auditum",
    "sum",
    "es",
    "est",
    "sunt",
    "erat",
    "fuit",
    "esse",
    "eris",
    "fuerat",
    "possum",
    "potest",
    "it",
    "ire",
    "ibat",
    "fert",
    "ferre",
    "tulit",
    "latum",
    "vult",
    "volumus",
    "nolo",
    "loquitur",
    "locutus",
    "sequuntur",
    "hortamur",
    "moritur",
    "utitur",
    "amatur",
    "monetur",
    "amabantur",
    "regebantur",
    "auditur",
]

_FIELDS = ("case", "number", "gender", "comparison", "person", "tense", "voice", "mood")
_INFLECTED = frozenset({"N", "ADJ", "V", "NUM", "PRON", "PACK"})
_POS = {
    "NounInfl": ("N", None),
    "AdjectiveInfl": ("ADJ", None),
    "VerbInfl": ("V", None),
    "VerbParticipleInfl": ("VPAR", "Part"),
    "SupineInfl": ("SUPINE", "Sup"),
    "PronounInfl": ("PRON", None),
    "NumberInfl": ("NUM", None),
}


def analyses(word: str) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for match in lookup.match_word(word):
        if match.dl_entry.pos not in _INFLECTED:
            continue
        ending = match.match_ending.replace("u", "v").replace("j", "i")
        stems = {
            str(n)
            for n in range(1, 5)
            if getattr(match, f"dl_stem{n}") == match.match_stem
        }
        inflections = definitions.get_possible_inflections(
            match.dl_entry, infl_ages=["X"], infl_frequencies=["A"]
        )
        entry = lookup.get_dictionary_string(match, header_only=True)
        for infl in inflections:
            kind = type(infl).__name__
            if (
                kind not in _POS
                or (infl.ending_vi or "") != ending
                or infl.stem not in stems
            ):
                continue
            pos, verb_form = _POS[kind]
            record = {f: getattr(infl, f) for f in _FIELDS if hasattr(infl, f)}
            found.append(
                {"pos": pos, "verb_form": verb_form, "entry": entry, "infl": record}
            )
    unique = {json.dumps(a, sort_keys=True): a for a in found}
    return sorted(unique.values(), key=lambda a: json.dumps(a, sort_keys=True))


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    fixture = [{"word": w, "analyses": analyses(w)} for w in WORDS]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(fixture, indent=1, ensure_ascii=False) + "\n")
    unknown = [e["word"] for e in fixture if not e["analyses"]]
    print(f"{len(fixture)} words written to {out}; none from Whitaker's: {unknown}")


if __name__ == "__main__":
    main()
