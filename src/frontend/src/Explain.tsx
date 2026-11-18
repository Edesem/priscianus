import { useState } from "react";
import { ApiError, explain } from "./api";
import type { ExplainResponse } from "./api";
import { describeFeatures } from "./features";
import TrustBadge from "./TrustBadge";

// The limit comes from ADR-005 (Decision 2). The API enforces it; we only show it.
const LIMIT_HINT = "Up to 25 words and 300 characters.";

export default function Explain() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ExplainResponse | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!text.trim() || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await explain({ text }));
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Something went wrong. Try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <section>
      <h2>Explain</h2>
      <form onSubmit={submit}>
        <label>
          Latin word or sentence
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            aria-describedby="explain-limit"
          />
        </label>
        <p id="explain-limit">{LIMIT_HINT}</p>
        <button type="submit" disabled={loading}>
          Explain this
        </button>
      </form>

      {loading && (
        <p role="status">
          Working on it. This usually takes a few seconds, and can take up to 7.
        </p>
      )}
      {error && <p role="alert">{error}</p>}

      {result && (
        <>
          <p>{result.text}</p>
          <ul>
            {result.words.map((word, i) => (
              <li key={i} aria-label={word.token}>
                <strong>{word.token}</strong>{" "}
                {word.claim ? (
                  <>
                    <span>{word.claim.lemma}</span>{" "}
                    {word.claim.state !== "verified" && (
                      <span>{describeFeatures(word.claim.features)}</span>
                    )}{" "}
                    <TrustBadge claim={word.claim} />
                  </>
                ) : (
                  <em>not explained</em>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
