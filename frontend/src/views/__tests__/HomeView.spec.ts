import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { makeListItem, testRouter } from '@/__tests__/helpers'
import { api } from '@/api/client'
import HomeView from '@/views/HomeView.vue'

// vi.mock is hoisted above the imports, so the real `api` cannot be referenced here;
// a type-only import() is fine because it disappears at compile time.
type Api = (typeof import('@/api/client'))['api']
vi.mock('@/api/client', () => ({
  api: { listArticles: vi.fn<Api['listArticles']>(), listFeeds: vi.fn<Api['listFeeds']>() },
}))

async function mountHome(path = '/') {
  const router = testRouter()
  router.push(path)
  await router.isReady()
  const wrapper = mount(HomeView, { global: { plugins: [router, createPinia()] } })
  await flushPromises()
  return { wrapper, router }
}

describe('HomeView', () => {
  beforeEach(() => {
    vi.mocked(api.listArticles)
      .mockReset()
      .mockResolvedValue({
        items: [makeListItem({ id: 1 }), makeListItem({ id: 2, title_tr: 'İkinci haber' })],
        total: 45,
        page: 1,
        size: 20,
      })
    vi.mocked(api.listFeeds).mockReset().mockResolvedValue([])
  })

  it('loads the last 24 hours by default', async () => {
    const { wrapper } = await mountHome()

    expect(api.listArticles).toHaveBeenCalledWith({ page: 1, size: 20, since_hours: 24 })
    expect(wrapper.findAll('article')).toHaveLength(2)
    expect(wrapper.text()).toContain('45 haber')
  })

  it('reads filters from the URL', async () => {
    await mountHome('/?range=7d&feed=3&q=gemini&page=2')

    expect(api.listArticles).toHaveBeenLastCalledWith({
      page: 2,
      size: 20,
      feed_id: 3,
      q: 'gemini',
      since_hours: 168,
    })
  })

  it('writes a changed filter to the URL and reloads from page 1', async () => {
    const { wrapper, router } = await mountHome('/?page=2')

    const button = wrapper.findAll('button').find((b) => b.text() === '48 saat')!
    await button.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.query).toEqual({ range: '48h' })
    expect(api.listArticles).toHaveBeenLastCalledWith({ page: 1, size: 20, since_hours: 48 })
  })

  it('searches after typing pauses', async () => {
    vi.useFakeTimers()
    const { wrapper, router } = await mountHome()

    await wrapper.find('input[type="search"]').setValue('gemini')
    expect(router.currentRoute.value.query).toEqual({}) // not yet: still debouncing
    await vi.advanceTimersByTimeAsync(300)

    expect(router.currentRoute.value.query).toEqual({ q: 'gemini' })
    vi.useRealTimers()
  })

  it('pages forward through the URL', async () => {
    const { wrapper, router } = await mountHome()

    await wrapper
      .findAll('button')
      .find((b) => b.text().includes('Sonraki'))!
      .trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.query).toEqual({ page: '2' })
  })

  it('shows an error with a retry button', async () => {
    vi.mocked(api.listArticles).mockRejectedValueOnce(new Error('Network error'))
    const { wrapper } = await mountHome()

    expect(wrapper.find('[role="alert"]').text()).toContain('Network error')
    await wrapper.find('[role="alert"] button').trigger('click')
    await flushPromises()

    expect(wrapper.findAll('article')).toHaveLength(2)
  })
})
