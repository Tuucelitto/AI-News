import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { testRouter } from '@/__tests__/helpers'
import { api, ApiError } from '@/api/client'
import { useSettingsStore } from '@/stores/settings'
import type { Feed } from '@/types/api'
import FeedsView from '@/views/FeedsView.vue'

function makeFeed(overrides: Partial<Feed> = {}): Feed {
  return {
    id: 1,
    name: 'OpenAI',
    url: 'https://openai.com/news/rss.xml',
    site_url: null,
    is_active: true,
    last_fetched_at: null,
    last_error: null,
    article_count: 6,
    ...overrides,
  }
}

async function mountFeeds({ admin }: { admin: boolean }) {
  const pinia = createPinia()
  setActivePinia(pinia)
  if (admin) useSettingsStore().adminKey = 'secret'
  const wrapper = mount(FeedsView, { global: { plugins: [testRouter(), pinia] } })
  await flushPromises()
  return wrapper
}

function button(wrapper: Awaited<ReturnType<typeof mountFeeds>>, text: string) {
  return wrapper.findAll('button').find((b) => b.text() === text)
}

describe('FeedsView', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.spyOn(api, 'listFeeds').mockResolvedValue([
      makeFeed(),
      makeFeed({ id: 2, name: 'Broken', last_error: 'HTTPStatusError: HTTP 500' }),
    ])
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('is read-only without an admin key', async () => {
    const wrapper = await mountFeeds({ admin: false })

    expect(wrapper.findAll('li')).toHaveLength(2)
    expect(wrapper.text()).toContain('Son hata: HTTPStatusError: HTTP 500')
    expect(wrapper.find('input[type="password"]').exists()).toBe(true)
    expect(button(wrapper, 'Sil')).toBeUndefined()
    expect(wrapper.find('input[type="url"]').exists()).toBe(false) // no add form
  })

  it('adds a feed and shows backend errors in Turkish', async () => {
    const create = vi
      .spyOn(api, 'createFeed')
      .mockRejectedValueOnce(new ApiError(409, 'A feed with this URL already exists'))
      .mockResolvedValueOnce(makeFeed({ id: 3, name: 'Hugging Face', url: 'https://hf.co/rss' }))
    const wrapper = await mountFeeds({ admin: true })

    const form = wrapper.findAll('form').find((f) => f.text().includes('Kaynak ekle'))!
    await form.find('input[type="url"]').setValue('https://hf.co/rss')
    await form.trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('Bu adresle bir kaynak zaten var.')

    await form.trigger('submit') // second try succeeds
    await flushPromises()

    expect(create).toHaveBeenLastCalledWith({ url: 'https://hf.co/rss', name: undefined }, 'secret')
    expect(wrapper.text()).toContain('“Hugging Face” eklendi')
    expect(wrapper.findAll('li')).toHaveLength(3)
  })

  it('asks for confirmation before deleting', async () => {
    const remove = vi.spyOn(api, 'deleteFeed').mockResolvedValue(undefined)
    const wrapper = await mountFeeds({ admin: true })

    await button(wrapper, 'Sil')!.trigger('click')
    expect(remove).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('6 haberiyle silinsin mi?')

    await button(wrapper, 'Evet, sil')!.trigger('click')
    await flushPromises()

    expect(remove).toHaveBeenCalledWith(1, 'secret')
    expect(wrapper.findAll('li')).toHaveLength(1)
  })

  it('shows the result of a manual refresh', async () => {
    vi.spyOn(api, 'refreshFeed').mockResolvedValue({
      new_articles: 3,
      not_modified: false,
      error: null,
      queued_for_summary: 2,
      skipped: 1,
    })
    const wrapper = await mountFeeds({ admin: true })

    await button(wrapper, 'Yenile')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('3 yeni haber (2 özet kuyruğunda, 1 kısa).')
  })
})
