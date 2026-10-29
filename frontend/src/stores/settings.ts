import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

const ADMIN_KEY_STORAGE = 'ai-news:admin-key'

// localStorage can throw (private mode, blocked storage); the app must still work without it.
function readStoredKey(): string {
  try {
    return localStorage.getItem(ADMIN_KEY_STORAGE) ?? ''
  } catch {
    return ''
  }
}

function storeKey(value: string): void {
  try {
    if (value) localStorage.setItem(ADMIN_KEY_STORAGE, value)
    else localStorage.removeItem(ADMIN_KEY_STORAGE)
  } catch {
    // Not persisted; the key stays in memory for this tab.
  }
}

/** The admin key for write endpoints, remembered in this browser only. */
export const useSettingsStore = defineStore('settings', () => {
  const adminKey = ref(readStoredKey())
  const hasAdminKey = computed(() => adminKey.value.length > 0)

  watch(adminKey, storeKey)

  return { adminKey, hasAdminKey }
})
