import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

import { api, ApiError } from '@/api/client'
import { useSettingsStore } from '@/stores/settings'

const KEY_STORAGE = 'ai-news:admin-key'
const THEME_STORAGE = 'ai-news:theme'

describe('settings store', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.classList.remove('dark')
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('admin key', () => {
    it('saves a key only after the backend accepts it', async () => {
      const check = vi.spyOn(api, 'checkAdminKey').mockResolvedValue(undefined)
      const settings = useSettingsStore()

      const error = await settings.saveAdminKey('secret')
      await nextTick() // watchers run asynchronously

      expect(check).toHaveBeenCalledWith('secret')
      expect(error).toBeNull()
      expect(settings.hasAdminKey).toBe(true)
      expect(localStorage.getItem(KEY_STORAGE)).toBe('secret')

      setActivePinia(createPinia()) // like reloading the page
      expect(useSettingsStore().adminKey).toBe('secret')
    })

    it('rejects a wrong key with a Turkish message', async () => {
      vi.spyOn(api, 'checkAdminKey').mockRejectedValue(new ApiError(401, 'Invalid'))
      const settings = useSettingsStore()

      const error = await settings.saveAdminKey('wrong')

      expect(error).toBe('Yönetici anahtarı yanlış.')
      expect(settings.hasAdminKey).toBe(false)
    })

    it('forgets the key', async () => {
      localStorage.setItem(KEY_STORAGE, 'secret')
      const settings = useSettingsStore()

      settings.forgetAdminKey()
      await nextTick()

      expect(localStorage.getItem(KEY_STORAGE)).toBeNull()
    })
  })

  describe('theme', () => {
    it('cycles system → light → dark and applies the dark class', async () => {
      const settings = useSettingsStore()
      expect(settings.theme).toBe('system')

      settings.cycleTheme()
      await nextTick()
      expect(settings.theme).toBe('light')
      expect(document.documentElement.classList.contains('dark')).toBe(false)

      settings.cycleTheme()
      await nextTick()
      expect(settings.theme).toBe('dark')
      expect(document.documentElement.classList.contains('dark')).toBe(true)
      expect(localStorage.getItem(THEME_STORAGE)).toBe('dark')

      settings.cycleTheme()
      await nextTick()
      expect(settings.theme).toBe('system')
      expect(localStorage.getItem(THEME_STORAGE)).toBeNull() // system is the default
    })

    it('restores the saved theme', () => {
      localStorage.setItem(THEME_STORAGE, 'dark')

      expect(useSettingsStore().theme).toBe('dark')
      expect(document.documentElement.classList.contains('dark')).toBe(true)
    })
  })
})
