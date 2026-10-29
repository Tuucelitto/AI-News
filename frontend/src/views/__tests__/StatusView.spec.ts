import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { makeArticle, makeListItem, testRouter } from '@/__tests__/helpers'
import { api } from '@/api/client'
import { useSettingsStore } from '@/stores/settings'
import type { QueueStatus } from '@/types/api'
import StatusView from '@/views/StatusView.vue'

const inMinutes = (minutes: number) => new Date(Date.now() + minutes * 60_000).toISOString()

function makeStatus(): QueueStatus {
  return {
    counts: { new: 0, pending: 4, processing: 0, done: 46, skipped: 0, failed: 1 },
    models: [
      {
        model: 'gemini-3.8-flash',
        role: 'primary',
        requests_today: 7,
        daily_limit: 18,
        quota_resets_at: inMinutes(600),
        paused_until: inMinutes(3.5), // shows as "3 dakika": partial minutes are truncated
      },
      {
        model: 'gemini-3.5-flash-lite',
        role: 'fallback',
        requests_today: 9,
        daily_limit: 45,
        quota_resets_at: inMinutes(600),
        paused_until: null,
      },
    ],
    scheduler_running: true,
    last_fetch_at: inMinutes(-20),
    next_fetch_at: inMinutes(40),
  }
}

async function mountStatus({ admin }: { admin: boolean }) {
  const pinia = createPinia()
  setActivePinia(pinia)
  if (admin) useSettingsStore().adminKey = 'secret'
  const wrapper = mount(StatusView, { global: { plugins: [testRouter(), pinia] } })
  await flushPromises()
  return wrapper
}

describe('StatusView', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.spyOn(api, 'queueStatus').mockResolvedValue(makeStatus())
    vi.spyOn(api, 'listArticles').mockResolvedValue({
      items: [makeListItem({ id: 5, title: 'Blocked story', summary_status: 'failed' })],
      total: 1,
      page: 1,
      size: 50,
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('shows counts, quota usage, pauses and the scheduler', async () => {
    const wrapper = await mountStatus({ admin: false })
    const text = wrapper.text()

    expect(text).toContain('Kuyrukta4')
    expect(text).toContain('Özetlendi46')
    expect(text).toContain('7 / 18 istek')
    expect(text).toContain('9 / 45 istek')
    expect(text).toContain('duraklatıldı, 3 dakika sonra devam edecek')
    expect(text).toContain('Çalışıyor')
    expect(text).toContain('20 dakika önce')
    expect(api.listArticles).toHaveBeenCalledWith({ status: 'failed', size: 50 })
    wrapper.unmount() // stops polling
  })

  it('puts a failed article back in the queue', async () => {
    const resummarize = vi
      .spyOn(api, 'resummarizeArticle')
      .mockResolvedValue(makeArticle({ id: 5, summary_status: 'pending' }))
    const wrapper = await mountStatus({ admin: true })

    expect(wrapper.text()).toContain('Blocked story')
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Tekrar özetle')!
      .trigger('click')
    await flushPromises()

    expect(resummarize).toHaveBeenCalledWith(5, 'secret')
    expect(api.queueStatus).toHaveBeenCalledTimes(2) // refreshed after the retry
    wrapper.unmount()
  })
})
