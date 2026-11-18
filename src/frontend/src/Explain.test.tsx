import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import Explain from "./Explain";

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

const reply = {
  text: "Rex means king. Regem is the object of the sentence.",
  model: "m",
  prompt_id: "explain-v1",
  dropped_claims: 0,
  words: [
    {
      token: "regem",
      claim: {
        form: "regem",
        lemma: "rex",
        upos: "NOUN",
        features: { Case: "Acc", Number: "Sing" },
        state: "verified",
        other_readings: [],
      },
      note: null,
    },
    {
      token: "quoque",
      claim: null,
      note: null,
    },
  ],
};

async function submit(text: string) {
  const user = userEvent.setup();
  render(<Explain />);
  await user.type(screen.getByRole("textbox"), text);
  await user.click(screen.getByRole("button", { name: "Explain this" }));
}

test("shows the input limit before anything is submitted", () => {
  render(<Explain />);
  expect(screen.getByText(/25 words/)).toBeInTheDocument();
  expect(screen.getByText(/300 characters/)).toBeInTheDocument();
});

test("shows the explanation, then each word with lemma, parse and badge", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json(reply)),
  );
  await submit("regem quoque");

  expect(await screen.findByText(reply.text)).toBeInTheDocument();
  const item = screen.getByRole("listitem", { name: "regem" });
  expect(item).toHaveTextContent("rex");
  expect(item).toHaveTextContent("accusative singular of rex");
  expect(item).toHaveTextContent("Verified");
});

test("a word with no claim is shown as not explained", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json(reply)),
  );
  await submit("regem quoque");

  const item = await screen.findByRole("listitem", { name: "quoque" });
  expect(item).toHaveTextContent("not explained");
});

test("shows a loading message while waiting, then removes it", async () => {
  let finish: (r: Response) => void = () => {};
  vi.stubGlobal(
    "fetch",
    vi.fn(() => new Promise<Response>((resolve) => (finish = resolve))),
  );
  await submit("regem");

  expect(screen.getByRole("status")).toHaveTextContent(/few seconds/i);
  finish(Response.json(reply));
  await screen.findByText(reply.text);
  expect(screen.queryByRole("status")).toBeNull();
});

test("a 429 shows the daily limit message", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json({ error: "daily_limit", message: "raw" }, { status: 429 }),
    ),
  );
  await submit("regem");

  expect(await screen.findByRole("alert")).toHaveTextContent(
    /daily limit reached/i,
  );
});

test("an empty box does not call the API", async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  const user = userEvent.setup();
  render(<Explain />);
  await user.click(screen.getByRole("button", { name: "Explain this" }));
  expect(fetchMock).not.toHaveBeenCalled();
});
