import { useId, useState } from "react";
import type { Claim, ClaimState, Reading } from "./api";
import { describeFeatures } from "./features";

// Labels, shapes and colours follow ADR-005, Decision 5. The label is always text,
// so colour is never the only signal.
const SHAPES: Record<ClaimState, React.ReactNode> = {
  verified: (
    <>
      <circle cx="8" cy="8" r="7" />
      <path d="M4.5 8.5l2.5 2.5 4.5-5" />
    </>
  ),
  ambiguous: (
    <>
      <circle cx="8" cy="8" r="7" />
      <path d="M4 6h8M10 4l2 2-2 2M12 10H4M6 8l-2 2 2 2" />
    </>
  ),
  unverifiable: (
    <>
      <circle cx="8" cy="8" r="7" strokeDasharray="2.5 2" />
      <path d="M6 6.5a2 2 0 1 1 3 1.7c-.7.4-1 .8-1 1.5M8 12v.1" />
    </>
  ),
  disputed: (
    <>
      <path d="M8 1.5l7 12.5H1z" />
      <path d="M8 6v4M8 11.7v.1" />
    </>
  ),
};

function label(claim: Claim): string {
  if (claim.state === "verified") return "Verified";
  if (claim.state === "unverifiable") return "Not in the database";
  if (claim.state === "disputed") return "Disagrees with the database";
  const n = claim.other_readings.length;
  return `Verified, ${n} other reading${n === 1 ? "" : "s"}`;
}

const MEANING: Record<ClaimState, string> = {
  verified: "matches the database",
  ambiguous: "matches the database, and the word has other readings",
  unverifiable: "the database cannot check this word",
  disputed: "does not match the database",
};

function say(item: {
  lemma: string;
  features: Claim["features"] | string;
  form?: string;
}): string {
  const words = describeFeatures(item.features);
  return words ? `${words} of ${item.lemma}` : `${item.form} of ${item.lemma}`;
}

function Readings({ readings }: { readings: Reading[] }) {
  return (
    <ul>
      {readings.map((reading, i) => (
        <li key={i}>{say(reading)}</li>
      ))}
    </ul>
  );
}

function Details({ claim }: { claim: Claim }) {
  if (claim.state === "ambiguous") {
    return <Readings readings={claim.other_readings} />;
  }
  if (claim.state === "unverifiable") {
    return (
      <p>
        The database does not hold this word, or it holds no adverbs,
        prepositions or conjunctions. It has not been checked.
      </p>
    );
  }
  return (
    <>
      <p>The claim: {say(claim)}</p>
      <Readings readings={claim.other_readings} />
      <p>The database can be incomplete. This may still be right.</p>
    </>
  );
}

export default function TrustBadge({ claim }: { claim: Claim }) {
  const [open, setOpen] = useState(false);
  const detailsId = useId();
  const text = label(claim);
  const icon = (
    <svg
      className="trust-icon"
      viewBox="0 0 16 16"
      width="16"
      height="16"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {SHAPES[claim.state]}
    </svg>
  );

  // A verified claim has nothing to expand, so it is plain text, not a button.
  if (claim.state === "verified") {
    return (
      <span className="trust-badge trust-verified">
        {icon}
        <span>{text}</span>
        <span className="trust-parse">{say(claim)}</span>
      </span>
    );
  }

  return (
    <span className="trust-wrap">
      <button
        type="button"
        className={`trust-badge trust-${claim.state}`}
        aria-expanded={open}
        aria-controls={detailsId}
        aria-label={`${text}: ${MEANING[claim.state]}. ${open ? "Hide" : "Show"} details`}
        onClick={() => setOpen(!open)}
      >
        {icon}
        <span>{text}</span>
      </button>
      <div id={detailsId} hidden={!open}>
        {open && <Details claim={claim} />}
      </div>
    </span>
  );
}
