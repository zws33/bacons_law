import { expect, test } from 'vitest'
import { makeSearchKey } from './makeSearchKey.js'

test("makeSearchKey should return a string with the correct format", () => {
  let label = "Hello, World! 123"
  expect(makeSearchKey(label)).toBe("hello world 123")
})
