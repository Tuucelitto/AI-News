import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'

import { usePolling } from '@/composables/usePolling'

function setVisibility(state: 'visible' | 'hidden') {
  Object.defineProperty(document, 'visibilityState', { value: state, configurable: true })
  document.dispatchEvent(new Event('visibilitychange'))
}

function mountPolling(fn: () => void) {
  const Component = defineComponent({
    setup() {
      usePolling(fn, 1000)
      return () => h('div')
    },
  })
  return mount(Component)
}

describe('usePolling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    setVisibility('visible')
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('calls immediately and then on every interval', () => {
    const fn = vi.fn<() => void>()
    mountPolling(fn)

    expect(fn).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(3000)
    expect(fn).toHaveBeenCalledTimes(4)
  })

  it('pauses while the tab is hidden and refreshes when it is back', () => {
    const fn = vi.fn<() => void>()
    mountPolling(fn)

    setVisibility('hidden')
    vi.advanceTimersByTime(5000)
    expect(fn).toHaveBeenCalledTimes(1)

    setVisibility('visible')
    expect(fn).toHaveBeenCalledTimes(2)
  })

  it('stops when the component is unmounted', () => {
    const fn = vi.fn<() => void>()
    const wrapper = mountPolling(fn)

    wrapper.unmount()
    vi.advanceTimersByTime(5000)
    setVisibility('visible') // the listener is gone too

    expect(fn).toHaveBeenCalledTimes(1)
  })
})
