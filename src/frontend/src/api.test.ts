import { afterEach, expect, test, vi } from "vitest";
import { ApiError, explain, grade } from "./api";

function replyWith(status: number, body: unknown) {
  const fetchMock = vi.fn(async () => Response.json(body, { status }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

test("a 429 becomes the 'daily limit reached' message", async () => {
  replyWith(429, {
    error: "daily_limit",
    message: "raw server text",
    resets_at: "2026-11-19T00:00:00+00:00",
  });
  const failure = explain({ text: "Arma virumque cano" });
  await expect(failure).rejects.toBeInstanceOf(ApiError);
  await expect(failure).rejects.toThrow(/daily limit reached/i);
});

test("a 503 spend cap becomes a message about the spending limit", async () => {
  replyWith(503, { error: "spend_cap", message: "raw server text" });
  await expect(explain({ text: "rex" })).rejects.toThrow(/spending limit/i);
});

test("a network failure becomes a 'could not reach the tutor' message", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
  );
  await expect(explain({ text: "rex" })).rejects.toThrow(
    /could not reach the tutor/i,
  );
});

test("a 422 shows the server's own message", async () => {
  replyWith(422, { error: "invalid_input", message: "Use at most 25 words." });
  await expect(explain({ text: "x" })).rejects.toThrow("Use at most 25 words.");
});

test("calls send the same X-Client-Id every time, as JSON to /api/<endpoint>", async () => {
  const fetchMock = replyWith(200, {
    correct: true,
    accepted: [],
    answer_is: [],
  });
  const item = {
    lemma: "rego",
    pos: "verb",
    features: { Tense: "Pres" },
    answer: "regit",
  };
  await grade(item);
  await grade(item);

  const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
  expect(calls[0][0]).toMatch(/\/api\/grade$/);
  expect(calls[0][1].method).toBe("POST");
  expect(JSON.parse(calls[0][1].body as string)).toEqual(item);
  const ids = calls.map(([, init]) =>
    new Headers(init.headers).get("X-Client-Id"),
  );
  expect(ids[0]).toBeTruthy();
  expect(ids[1]).toBe(ids[0]);
});

test("a success reply that is not JSON becomes a friendly message", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response("<html>oops</html>")),
  );
  await expect(explain({ text: "rex" })).rejects.toThrow(/unexpected reply/i);
});
