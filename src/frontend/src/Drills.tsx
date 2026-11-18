import { useState } from "react";
import { ApiError, drills, feedback, grade, messageFor } from "./api";
import type { DrillItem, DrillsResponse, FeedbackResponse } from "./api";
import { describeFeatures } from "./features";
import TrustBadge from "./TrustBadge";

// The limit comes from ADR-005 (Decision 1). The API enforces it; we only show it.
const REQUEST_HINT = "Up to 200 characters. Up to 10 items.";

// One drill: its own answer box, grade and feedback.
// The grade is free and shows at once. Feedback is a second call that costs one of
// the learner's daily requests, so we only ask for it after a wrong answer.
function DrillRow({ item }: { item: DrillItem }) {
  const [answer, setAnswer] = useState("");
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Awaited<
    ReturnType<typeof grade>
  > | null>(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [feedbackResult, setFeedbackResult] = useState<FeedbackResponse | null>(
    null,
  );
  const [feedbackError, setFeedbackError] = useState<string | null>(null);

  async function check(event: React.FormEvent) {
    event.preventDefault();
    if (!answer.trim() || checking) return;
    const request = {
      lemma: item.lemma,
      pos: item.pos,
      features: item.features,
      answer,
    };
    setChecking(true);
    setError(null);
    setResult(null);
    setFeedbackResult(null);
    setFeedbackError(null);
    try {
      const graded = await grade(request);
      setResult(graded);
      if (!graded.correct) {
        setFeedbackLoading(true);
        try {
          const reply = await feedback(request);
          setFeedbackResult(reply);
          if (reply.feedback_error) {
            setFeedbackError(messageFor(200, reply.feedback_error));
          }
        } catch (e) {
          setFeedbackError(
            e instanceof ApiError ? e.message : "Feedback is unavailable.",
          );
        } finally {
          setFeedbackLoading(false);
        }
      }
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Something went wrong. Try again.",
      );
    } finally {
      setChecking(false);
    }
  }

  const feedbackText = feedbackResult?.feedback;

  return (
    <li>
      <form onSubmit={check}>
        <label>
          {item.prompt}
          <input
            type="text"
            autoComplete="off"
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
          />
        </label>
        <button type="submit" disabled={checking}>
          Check
        </button>
      </form>
      {error && <p role="alert">{error}</p>}
      {result?.correct && <p role="status">Correct</p>}
      {result && !result.correct && (
        <div role="status">
          <p>Not quite</p>
          <p>Accepted: {result.accepted.join(", ")}</p>
          {result.answer_is.map((reading, i) => (
            <p key={i}>
              {reading.form} is the {describeFeatures(reading.features)} of{" "}
              {reading.lemma}.
            </p>
          ))}
        </div>
      )}
      {feedbackLoading && <p>Getting feedback…</p>}
      {feedbackError && <p>{feedbackError}</p>}
      {feedbackText && (
        <div>
          <p>{feedbackText.text}</p>
          <ul>
            {feedbackText.claims.map((claim, i) => (
              <li key={i}>
                <em>{claim.form}</em> <TrustBadge claim={claim} />
              </li>
            ))}
          </ul>
        </div>
      )}
    </li>
  );
}

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
            <DrillRow key={i} item={item} />
          ))}
        </ol>
      )}
    </section>
  );
}
