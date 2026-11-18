import type { Features } from "./api";

// Plain-English words for Universal Dependencies (UD) feature values.
// Keys are listed in the order we say them: "dative singular", "3rd person plural perfect active indicative".
const WORDS: Record<string, Record<string, string>> = {
  Case: {
    Nom: "nominative",
    Gen: "genitive",
    Dat: "dative",
    Acc: "accusative",
    Abl: "ablative",
    Voc: "vocative",
    Loc: "locative",
  },
  Gender: { Masc: "masculine", Fem: "feminine", Neut: "neuter" },
  Degree: { Pos: "positive", Cmp: "comparative", Sup: "superlative" },
  Person: { "1": "1st person", "2": "2nd person", "3": "3rd person" },
  Number: { Sing: "singular", Plur: "plural" },
  Tense: { Pres: "present", Past: "past", Fut: "future", Pqp: "pluperfect" },
  Aspect: { Perf: "perfect", Imp: "imperfect" },
  Voice: { Act: "active", Pass: "passive" },
  Mood: {
    Ind: "indicative",
    Sub: "subjunctive",
    Imp: "imperative",
  },
  VerbForm: {
    Inf: "infinitive",
    Part: "participle",
    Ger: "gerund",
    Gdv: "gerundive",
    Sup: "supine",
    Fin: "finite",
  },
};
const ORDER = Object.keys(WORDS);

/** "Case=Dat|Number=Sing" (or {Case: "Dat", Number: "Sing"}) becomes "dative singular". Unknown values are shown as they are. */
export function describeFeatures(features: Features | string): string {
  const pairs: Features =
    typeof features === "string"
      ? Object.fromEntries(
          features
            .split("|")
            .filter(Boolean)
            .map((pair) => pair.split("=") as [string, string]),
        )
      : features;
  const keys = [
    ...ORDER.filter((key) => key in pairs),
    ...Object.keys(pairs).filter((key) => !ORDER.includes(key)),
  ];
  return keys.map((key) => WORDS[key]?.[pairs[key]] ?? pairs[key]).join(" ");
}
