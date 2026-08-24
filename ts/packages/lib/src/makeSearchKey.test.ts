import { expect, test } from "vitest";
import { makeSearchKey } from "./makeSearchKey.js";

test("makeSearchKey should return a string with the correct format", () => {
  const label = "Héllo,  Wőrld! 123";
  expect(makeSearchKey(label)).toBe("hello world 123");
});
