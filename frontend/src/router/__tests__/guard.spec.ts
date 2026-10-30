import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import router from '@/router'
import { useSettingsStore } from '@/stores/settings'

describe('admin route guard', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('sends visitors from the status page to the home page', async () => {
    await router.push('/status')
    expect(router.currentRoute.value.name).toBe('home')
  })

  it('lets the owner open the status page', async () => {
    useSettingsStore().adminKey = 'key'
    await router.push('/status')
    expect(router.currentRoute.value.name).toBe('status')
  })
})
