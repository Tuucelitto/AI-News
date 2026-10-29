import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'

import { useSettingsStore } from '@/stores/settings'

const STORAGE_KEY = 'ai-news:admin-key'

describe('settings store', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('remembers the admin key in localStorage', async () => {
    const settings = useSettingsStore()
    expect(settings.hasAdminKey).toBe(false)

    settings.adminKey = 'secret'
    await nextTick() // watchers run asynchronously

    expect(localStorage.getItem(STORAGE_KEY)).toBe('secret')
    setActivePinia(createPinia()) // like reloading the page
    expect(useSettingsStore().adminKey).toBe('secret')
  })

  it('forgets the key when it is cleared', async () => {
    localStorage.setItem(STORAGE_KEY, 'secret')
    const settings = useSettingsStore()

    settings.adminKey = ''
    await nextTick()

    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
  })
})
