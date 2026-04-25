import '@testing-library/jest-dom'

// jsdom doesn't implement matchMedia — mock it so ChatContext doesn't crash
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
})

// jsdom doesn't implement crypto.randomUUID
Object.defineProperty(globalThis, 'crypto', {
  value: { randomUUID: () => Math.random().toString(36).slice(2) },
})
