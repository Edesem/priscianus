import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import type { Claim } from "./api";
import TrustBadge from "./TrustBadge";

const rex: Claim = {
  form: "rēgī",
  lemma: "rex",
  upos: "NOUN",
  features: { Case: "Dat", Number: "Sing" },
  state: "verified",
  other_readings: [],
};
const loc = {
  lemma: "rex",
  pos: "noun",
  form: "rēgī",
  features: "Case=Loc|Number=Sing",
};

test("each state shows its own text label", () => {
  const labels: [Claim["state"], Claim["other_readings"], string][] = [
    ["verified", [], "Verified"],
    ["ambiguous", [loc, loc], "Verified, 2 other readings"],
    ["unverifiable", [], "Not in the database"],
    ["disputed", [loc], "Disagrees with the database"],
  ];
  for (const [state, other_readings, label] of labels) {
    const { unmount } = render(
      <TrustBadge claim={{ ...rex, state, other_readings }} />,
    );
    expect(screen.getByText(label)).toBeInTheDocument();
    unmount();
  }
});

test("a verified claim shows its parse in plain words and has nothing to expand", () => {
  render(<TrustBadge claim={rex} />);
  expect(screen.getByText("dative singular of rex")).toBeInTheDocument();
  expect(screen.queryByRole("button")).toBeNull();
});

test("an ambiguous badge expands by keyboard to list the other readings", async () => {
  const user = userEvent.setup();
  render(
    <TrustBadge
      claim={{ ...rex, state: "ambiguous", other_readings: [loc] }}
    />,
  );
  const button = screen.getByRole("button", {
    name: /Verified, 1 other reading.*Show details/,
  });
  expect(button).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByText("locative singular of rex")).toBeNull();

  button.focus();
  await user.keyboard("{Enter}");
  expect(button).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByText("locative singular of rex")).toBeInTheDocument();
});

test("a disputed badge shows the claim, every reading and a caution", async () => {
  const user = userEvent.setup();
  render(
    <TrustBadge claim={{ ...rex, state: "disputed", other_readings: [loc] }} />,
  );
  await user.click(
    screen.getByRole("button", { name: /Disagrees with the database/ }),
  );
  expect(
    screen.getByText(/The claim: dative singular of rex/),
  ).toBeInTheDocument();
  expect(screen.getByText("locative singular of rex")).toBeInTheDocument();
  expect(
    screen.getByText(/The database can be incomplete/),
  ).toBeInTheDocument();
});

test("a not-in-the-database badge explains that nothing was checked", async () => {
  const user = userEvent.setup();
  render(<TrustBadge claim={{ ...rex, state: "unverifiable" }} />);
  await user.click(screen.getByRole("button", { name: /Not in the database/ }));
  expect(screen.getByText(/It has not been checked/)).toBeInTheDocument();
});
