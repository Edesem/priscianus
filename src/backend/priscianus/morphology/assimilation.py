"""Spelling variants from prefix assimilation: adfirmo/affirmo, inpiger/impiger (ADR-003).

The treebanks, PROIEL and ITTB especially, and learners who type medieval spellings write
the unassimilated prefix; Wiktionary writes the assimilated one. Neither is wrong, so
`variant_keys` is only a lookup-time fallback: the exact key always comes first.
"""

# Prefixes of a loose key (see `key_loose`) that are spellings of one another.
_GROUPS: tuple[tuple[str, ...], ...] = tuple(
    tuple(group.split("/"))
    for group in (
        "adc/acc",
        "adf/aff",
        "adg/agg",
        "adl/all",
        "adn/ann",
        "adp/app",
        "adq/acq",
        "adr/arr",
        "ads/ass",
        "adt/att",
        "inb/imb",
        "inl/ill",
        "inm/imm",
        "inp/imp",
        "inr/irr",
        "conb/comb",
        "conl/coll",
        "conm/comm",
        "conp/comp",
        "conr/corr",
        "obc/occ",
        "obf/off",
        "obp/opp",
        "subc/succ",
        "subf/suff",
        "subg/sugg",
        "subm/summ",
        "subp/supp",
        "subr/surr",
    )
)


def variant_keys(key: str) -> list[str]:
    """The other spellings of a loose key's prefix, or an empty list if it has none.

    `key` must already be a `key_loose` key. Only the start of the key changes, and the key
    itself is not in the result.
    """
    return [
        other + key[len(own) :]
        for group in _GROUPS
        for own in group
        if key.startswith(own) and len(key) > len(own)
        for other in group
        if other != own
    ]
