import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { makeArticle, testRouter } from '@/__tests__/helpers'
import { api, ApiError } from '@/api/client'
import ArticleView from '@/views/ArticleView.vue'

vi.mock('@/api/client', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/api/client')>()
  // Keep the real ApiError class; replace only the API call.
  return { ...original, api: { getArticle: vi.fn<(typeof original.api)['getArticle']>() } }
})

async function mountArticle(id = 1) {
  const wrapper = mount(ArticleView, {
    props: { id },
    global: { plugins: [testRouter(), createPinia()] },
  })
  await flushPromises()
  return wrapper
}

describe('ArticleView', () => {
  beforeEach(() => {
    vi.mocked(api.getArticle).mockReset()
  })

  it('shows the Turkish summary, key points and a safe link to the original', async () => {
    vi.mocked(api.getArticle).mockResolvedValue(makeArticle())
    const wrapper = await mountArticle()

    expect(wrapper.find('h1').text()).toBe('Yeni bir model')
    expect(wrapper.text()).toContain('A new model') // original title
    expect(wrapper.findAll('li').map((li) => li.text())).toEqual(['Daha hızlı', 'Daha ucuz'])
    const link = wrapper.find('a[target="_blank"]')
    expect(link.attributes('href')).toBe('https://openai.example.com/model')
    expect(link.attributes('rel')).toBe('noopener noreferrer')
    expect(wrapper.text()).toContain('gemini-3.8-flash')
  })

  it('explains a missing summary and shows the original description', async () => {
    vi.mocked(api.getArticle).mockResolvedValue(
      makeArticle({ title_tr: null, summary_tr: null, key_points: null, summary_status: 'failed' }),
    )
    const wrapper = await mountArticle()

    expect(wrapper.text()).toContain('Türkçe özet oluşturulamadı')
    expect(wrapper.find('p[lang="en"]:not(.text-sm)').text()).toBe(
      'The model is faster and cheaper.',
    )
  })

  it('shows "not found" for a 404', async () => {
    vi.mocked(api.getArticle).mockRejectedValue(new ApiError(404, 'Article not found'))
    const wrapper = await mountArticle(999)

    expect(wrapper.text()).toContain('Haber bulunamadı')
  })
})
