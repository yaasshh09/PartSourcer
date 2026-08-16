import '@testing-library/jest-dom'
import { beforeEach, afterEach } from 'vitest'

// React reports duplicate keys, bad props and act() violations through
// console.error and then renders anyway, so a real defect can sit behind a
// green suite. Fail the test instead.
//
// Plain assignment rather than vi.spyOn on purpose: several test files call
// vi.restoreAllMocks() in their own beforeEach, which would tear a spy back
// out and silently disarm this.
const realError = console.error
let seen = []

// React passes its warnings as a format string plus arguments, so join them
// the way the console would rather than printing raw %s placeholders.
function format(args) {
  const [first, ...rest] = args
  if (typeof first !== 'string' || !first.includes('%')) {
    return args.map(String).join(' ')
  }
  let i = 0
  const filled = first.replace(/%[sdifoOc]/g, () => (i < rest.length ? String(rest[i++]) : ''))
  return [filled, ...rest.slice(i)].map(String).join(' ').trim()
}

beforeEach(() => {
  seen = []
  console.error = (...args) => { seen.push(format(args)) }
})

afterEach(() => {
  console.error = realError
  if (seen.length) {
    const found = seen.join('\n')
    seen = []
    throw new Error('console.error was called during this test:\n' + found)
  }
})
