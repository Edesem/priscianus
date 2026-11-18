import { useState } from "react";
import { ApiError, drills } from "./api";
import type { DrillsResponse } from "./api";

// The limit comes from ADR-005 (Decision 1). The API enforces it; we only show it.
const REQUEST_HINT = "Up to 200 characters. Up to 10 items.";

export default function Drills() {
  const [request, setRequest] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DrillsResponse | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!request.trim() || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await drills({ request }));
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
      <h2>Drills</h2>
      <form onSubmit={submit}>
        <label>
          What do you want to practise?
          <textarea
            value={request}
            onChange={(e) => setRequest(e.target.value)}
            maxLength={200}
            aria-describedby="drills-hint"
          />
        </label>
        <p id="drills-hint">
          For example: "10 perfect-tense verbs from the 3rd conjugation".{" "}
          {REQUEST_HINT}
        </p>
        <button type="submit" disabled={loading}>
          Get drills
        </button>
      </form>

      <p>Macrons are optional: amāvērunt and amaverunt both count.</p>

      {loading && (
        <p role="status">Working on it. This usually takes a few seconds.</p>
      )}
      {error && <p role="alert">{error}</p>}

      {result?.message && <p role="status">{result.message}</p>}
      {result && result.items.length > 0 && (
        <ol>
          {result.items.map((item, i) => (
            <li key={i}>
              <label>
                {item.prompt}
                <input type="text" autoComplete="off" />
              </label>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
