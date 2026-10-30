import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

import { api } from '@/api/client'
import { errorMessage } from '@/utils/errors'
import { readStorage, writeStorage } from '@/utils/storage'

const ADMIN_KEY_STORAGE = 'ai-news:admin-key'
const THEME_STORAGE = 'ai-news:theme' // also read by the inline script in index.html

export type Theme = 'system' | 'light' | 'dark'
const THEMES: Theme[] = ['system', 'light', 'dark']

function systemPrefersDark(): boolean {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
}

export const useSettingsStore = defineStore('settings', () => {
  // --- Admin key (remembered in this browser only) ---
  const adminKey = ref(readStorage(ADMIN_KEY_STORAGE) ?? '')
  const hasAdminKey = computed(() => adminKey.value.length > 0)
  watch(adminKey, (value) => writeStorage(ADMIN_KEY_STORAGE, value))

  /** Checks the key with the backend and saves it if valid. Returns an error message or null. */
  async function saveAdminKey(key: string): Promise<string | null> {
    try {
      await api.checkAdminKey(key)
    } catch (e) {
      return errorMessage(e)
    }
    adminKey.value = key
    return null
  }

  function forgetAdminKey(): void {
    adminKey.value = ''
  }

  // --- Theme ---
  const stored = readStorage(THEME_STORAGE)
  const theme = ref<Theme>(THEMES.includes(stored as Theme) ? (stored as Theme) : 'system')

  function applyTheme(): void {
    const dark = theme.value === 'dark' || (theme.value === 'system' && systemPrefersDark())
    document.documentElement.classList.toggle('dark', dark)
  }

  function setTheme(value: Theme): void {
    theme.value = value
  }

  watch(theme, (value) => {
    writeStorage(THEME_STORAGE, value === 'system' ? '' : value)
    applyTheme()
  })
  // Follow the operating system live while the theme is "system".
  window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener('change', applyTheme)
  applyTheme()

  return { adminKey, hasAdminKey, saveAdminKey, forgetAdminKey, theme, setTheme }
})
