import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import Drills from "./Drills";

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

const reply = {
  message: null,
  shortfall: 0,
  items: [
    {
      lemma: "rego",
      pos: "verb",
      features: { Person: "3", Number: "Plur" },
      prompt: "Give the 3rd person plural perfect active indicative of rego.",
    },
    {
      lemma: "rex",
      pos: "noun",
      features: { Case: "Dat", Number: "Plur" },
      prompt: "Give the dative plural of rex.",
    },
  ],
};

async function submit(request: string) {
  const user = userEvent.setup();
  render(<Drills />);
  await user.type(
    screen.getByLabelText(/what do you want to practise/i),
    request,
  );
  await user.click(screen.getByRole("button", { name: "Get drills" }));
}

test("tells the learner that macrons are optional", () => {
  render(<Drills />);
  expect(screen.getByText(/macrons are optional/i)).toBeInTheDocument();
});

test("shows each item with its own answer box", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json(reply)),
  );
  await submit("rego perfect, rex plural");

  for (const item of reply.items) {
    expect(await screen.findByText(item.prompt)).toBeInTheDocument();
    expect(screen.getByLabelText(item.prompt)).toBeInTheDocument();
  }
});

test("a request the generator cannot meet shows its message and no items", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json({
        message: "Nouns have no person, so I cannot make that drill.",
        shortfall: 10,
        items: [],
      }),
    ),
  );
  await submit("1st person of a noun");

  expect(await screen.findByRole("status")).toHaveTextContent(
    "Nouns have no person",
  );
  expect(screen.queryByRole("textbox", { name: /give the/i })).toBeNull();
});

test("shows a loading message while waiting, then removes it", async () => {
  let finish: (r: Response) => void = () => {};
  vi.stubGlobal(
    "fetch",
    vi.fn(() => new Promise<Response>((resolve) => (finish = resolve))),
  );
  await submit("rex plural");

  expect(screen.getByRole("status")).toHaveTextContent(/working on it/i);
  finish(Response.json(reply));
  await screen.findByText(reply.items[0].prompt);
  expect(screen.queryByText(/working on it/i)).toBeNull();
});

test("a 429 shows the daily limit message", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json({ error: "daily_limit", message: "raw" }, { status: 429 }),
    ),
  );
  await submit("rex plural");

  expect(await screen.findByRole("alert")).toHaveTextContent(
    /daily limit reached/i,
  );
});

test("an empty request does not call the API", async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  const user = userEvent.setup();
  render(<Drills />);
  await user.click(screen.getByRole("button", { name: "Get drills" }));
  expect(fetchMock).not.toHaveBeenCalled();
});

// --- Answering and grading (#113) ---

const claim = {
  form: "rexerunt",
  lemma: "rego",
  upos: "VERB",
  features: { Person: "3", Number: "Plur" },
  state: "verified",
  other_readings: [],
};

const wrongGrade = {
  correct: false,
  accepted: ["rexerunt", "rexere"],
  answer_is: [
    {
      lemma: "rego",
      form: "regunt",
      features: "Mood=Ind|Number=Plur|Person=3|Tense=Pres",
      same_lemma: true,
    },
  ],
};

// Loads the drills, then types an answer into the first box and checks it.
// `routes` maps an API path to the JSON reply (or a function that makes one).
async function answerFirst(
  routes: Record<string, () => Response | Promise<Response>>,
  answer: string,
) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const path = new URL(url, "http://x").pathname;
      return routes[path]();
    }),
  );
  await submit("rego perfect, rex plural");
  const user = userEvent.setup();
  const box = await screen.findByLabelText(reply.items[0].prompt);
  if (answer) await user.type(box, answer);
  await user.click(screen.getAllByRole("button", { name: "Check" })[0]);
}

test("a right answer shows 'Correct' and asks for no feedback", async () => {
  const feedbackCalls = vi.fn();
  await answerFirst(
    {
      "/api/drills": () => Response.json(reply),
      "/api/grade": () =>
        Response.json({ correct: true, accepted: ["rexerunt"], answer_is: [] }),
      "/api/feedback": () => {
        feedbackCalls();
        return Response.json({});
      },
    },
    "rexerunt",
  );

  expect(await screen.findByText("Correct")).toBeInTheDocument();
  expect(feedbackCalls).not.toHaveBeenCalled();
});

test("a wrong answer shows the accepted forms, what was typed, and the feedback with badges", async () => {
  await answerFirst(
    {
      "/api/drills": () => Response.json(reply),
      "/api/grade": () => Response.json(wrongGrade),
      "/api/feedback": () =>
        Response.json({
          grade: wrongGrade,
          feedback: {
            text: "You gave the present tense; the perfect ends in -erunt.",
            model: "m",
            prompt_id: "feedback-v1",
            claims: [claim],
          },
          feedback_error: null,
        }),
    },
    "regunt",
  );

  expect(await screen.findByText("Not quite")).toBeInTheDocument();
  expect(screen.getByText(/rexerunt, rexere/)).toBeInTheDocument();
  expect(screen.getByText(/regunt is/i)).toBeInTheDocument();
  expect(
    await screen.findByText(/the perfect ends in -erunt/i),
  ).toBeInTheDocument();
  expect(screen.getByText("Verified")).toBeInTheDocument();
});

test("a wrong answer still shows the grade when the feedback call fails", async () => {
  await answerFirst(
    {
      "/api/drills": () => Response.json(reply),
      "/api/grade": () => Response.json(wrongGrade),
      "/api/feedback": () =>
        Response.json({
          grade: wrongGrade,
          feedback: null,
          feedback_error: {
            error: "daily_limit",
            message: "raw",
            resets_at: null,
          },
        }),
    },
    "regunt",
  );

  expect(await screen.findByText("Not quite")).toBeInTheDocument();
  expect(screen.getByText(/rexerunt, rexere/)).toBeInTheDocument();
  expect(await screen.findByText(/daily limit reached/i)).toBeInTheDocument();
});

test("an empty answer does not call the grade endpoint", async () => {
  const gradeCalls = vi.fn();
  await answerFirst(
    {
      "/api/drills": () => Response.json(reply),
      "/api/grade": () => {
        gradeCalls();
        return Response.json({});
      },
    },
    "",
  );
  expect(gradeCalls).not.toHaveBeenCalled();
});
