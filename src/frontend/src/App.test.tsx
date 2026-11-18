import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import App from "./App";

test("starts on Explain and switches to Drills and back", async () => {
  const user = userEvent.setup();
  render(<App />);
  expect(screen.getByRole("heading", { name: "Explain" })).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Drills" }));
  expect(screen.getByRole("heading", { name: "Drills" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Explain" })).toBeNull();

  await user.click(screen.getByRole("button", { name: "Explain" }));
  expect(screen.getByRole("heading", { name: "Explain" })).toBeInTheDocument();
});

test("shows the Wiktionary attribution on every view", async () => {
  const user = userEvent.setup();
  render(<App />);
  const footer = screen.getByRole("contentinfo");
  expect(footer).toHaveTextContent(
    "Wiktionary (English Wiktionary contributors)",
  );
  expect(footer).toHaveTextContent("CC BY-SA 4.0");

  await user.click(screen.getByRole("button", { name: "Drills" }));
  expect(screen.getByRole("contentinfo")).toHaveTextContent("Wiktionary");
});
