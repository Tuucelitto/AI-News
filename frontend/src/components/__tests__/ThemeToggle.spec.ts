import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import ThemeToggle from '@/components/ThemeToggle.vue'
import { useSettingsStore } from '@/stores/settings'

function checked(wrapper: ReturnType<typeof mount>) {
  return wrapper.find('[role="radio"][aria-checked="true"]').attributes('aria-label')
}

describe('ThemeToggle', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('selects a theme on click', async () => {
    const wrapper = mount(ThemeToggle)
    expect(checked(wrapper)).toBe('Sistem')

    await wrapper.find('[aria-label="Koyu"]').trigger('click')

    expect(checked(wrapper)).toBe('Koyu')
    expect(useSettingsStore().theme).toBe('dark')
  })

  it('moves the selection with the arrow keys', async () => {
    const wrapper = mount(ThemeToggle)
    const group = wrapper.find('[role="radiogroup"]')

    await group.trigger('keydown', { key: 'ArrowRight' })
    expect(checked(wrapper)).toBe('Açık')

    await group.trigger('keydown', { key: 'ArrowLeft' })
    await group.trigger('keydown', { key: 'ArrowLeft' }) // wraps around
    expect(checked(wrapper)).toBe('Koyu')
  })

  it('makes only the selected option reachable with Tab', () => {
    const wrapper = mount(ThemeToggle)

    const tabStops = wrapper.findAll('[role="radio"]').map((b) => b.attributes('tabindex'))
    expect(tabStops).toEqual(['0', '-1', '-1'])
  })
})
