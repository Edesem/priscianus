import { render } from "@testing-library/react";
import { expect, test } from "vitest";
import App from "./App";

test("renders the app", () => {
  const { container } = render(<App />);
  expect(container).not.toBeEmptyDOMElement();
});
