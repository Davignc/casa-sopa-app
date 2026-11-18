import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

afterEach(() => {
  cleanup()
  sessionStorage.clear()
  vi.useRealTimers()
})

// O jsdom não tem ResizeObserver (os gráficos usam).
class ResizeObserverFalso {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverFalso as unknown as typeof ResizeObserver

// Não existe no jsdom.
window.scrollTo = vi.fn() as unknown as typeof window.scrollTo
Element.prototype.scrollIntoView ??= vi.fn()
URL.createObjectURL ??= vi.fn(() => 'blob:falso')
URL.revokeObjectURL ??= vi.fn()
