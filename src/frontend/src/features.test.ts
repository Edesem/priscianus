import { expect, test } from "vitest";
import { describeFeatures } from "./features";

test("turns UD features into plain English, in reading order", () => {
  expect(describeFeatures({ Number: "Sing", Case: "Dat" })).toBe(
    "dative singular",
  );
});

test("accepts the index's pipe-separated string and keeps unknown values", () => {
  expect(describeFeatures("Case=Loc|Number=Sing")).toBe("locative singular");
  expect(describeFeatures({ Case: "Dat", Odd: "Thing" })).toBe("dative Thing");
});
