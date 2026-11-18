// The one place the front end talks to the API. Types follow ADR-005, Decision 1.

export type Features = Record<string, string>;

export type ClaimState = "verified" | "ambiguous" | "disputed" | "unverifiable";

export interface Reading {
  lemma: string;
  pos: string;
  form: string;
  features: string;
}

export interface Claim {
  form: string;
  lemma: string;
  upos: string;
  features: Features;
  state: ClaimState;
  other_readings: Reading[];
}

export interface ExplainRequest {
  text: string;
}

export interface ExplainResponse {
  text: string;
  model: string;
  prompt_id: string;
  dropped_claims: number;
  words: { token: string; claim: Claim | null; note: string | null }[];
}

export interface DrillsRequest {
  request: string;
  count?: number;
}

export interface DrillItem {
  lemma: string;
  pos: string;
  features: Features;
  prompt: string;
}

export interface DrillsResponse {
  message: string | null;
  shortfall: number;
  items: DrillItem[];
}

export interface GradeRequest {
  lemma: string;
  pos: string;
  features: Features;
  answer: string;
}

export interface GradeResponse {
  correct: boolean;
  accepted: string[];
  answer_is: {
    lemma: string;
    form: string;
    features: string;
    same_lemma: boolean;
  }[];
}

export interface FeedbackResponse {
  grade: GradeResponse;
  feedback: {
    text: string;
    model: string;
    prompt_id: string;
    claims: Claim[];
  } | null;
  feedback_error: {
    error: string;
    message: string;
    resets_at: string | null;
  } | null;
}

/** An error whose `message` is plain English, safe to show to the learner. */
export class ApiError extends Error {}

const BASE_URL: string = import.meta.env.VITE_API_URL ?? "";

// The API counts daily limits per browser, so every call sends the same random ID.
function clientId(): string {
  try {
    const saved = localStorage.getItem("clientId");
    if (saved) return saved;
    const fresh = crypto.randomUUID();
    localStorage.setItem("clientId", fresh);
    return fresh;
  } catch {
    return crypto.randomUUID(); // storage blocked: the IP limit still applies
  }
}

function messageFor(
  status: number,
  body: { error?: string; message?: string } | null,
): string {
  if (body?.error === "daily_limit") {
    return "Daily limit reached. You can ask again after midnight UTC.";
  }
  if (body?.error === "spend_cap") {
    return "The tutor has reached its spending limit for today. Please come back tomorrow.";
  }
  if (body?.message) return body.message;
  return `Something went wrong (error ${status}). Please try again.`;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Client-Id": clientId(),
      },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError(
      "Could not reach the tutor. Check your connection and try again.",
    );
  }
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new ApiError(messageFor(response.status, errorBody));
  }
  return (await response.json()) as T;
}

export const explain = (req: ExplainRequest) =>
  post<ExplainResponse>("/api/explain", req);
export const drills = (req: DrillsRequest) =>
  post<DrillsResponse>("/api/drills", req);
export const grade = (req: GradeRequest) =>
  post<GradeResponse>("/api/grade", req);
export const feedback = (req: GradeRequest) =>
  post<FeedbackResponse>("/api/feedback", req);
