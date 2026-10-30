import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it } from 'vitest'

import { makeListItem, testRouter } from '@/__tests__/helpers'
import ArticleCard from '@/components/ArticleCard.vue'
import type { ArticleListItem } from '@/types/api'

function mountCard(article: ArticleListItem) {
  return mount(ArticleCard, {
    props: { article },
    global: { plugins: [testRouter(), createPinia()] },
  })
}

describe('ArticleCard', () => {
  it('shows the Turkish title and summary of a summarized article', () => {
    const wrapper = mountCard(makeListItem())

    expect(wrapper.find('h2').text()).toBe('Yeni bir model')
    expect(wrapper.text()).toContain('Model daha hızlı ve daha ucuz.')
    expect(wrapper.text()).toContain('OpenAI')
    expect(wrapper.text()).toContain('2 saat önce')
    expect(wrapper.text()).not.toContain('Özet') // no status badge when done
    expect(wrapper.find('a').attributes('href')).toBe('/articles/1')
  })

  it('falls back to the English text while the summary is pending', () => {
    const wrapper = mountCard(
      makeListItem({ title_tr: null, summary_tr: null, summary_status: 'pending' }),
    )

    expect(wrapper.find('h2').text()).toBe('A new model')
    expect(wrapper.find('p[lang="en"]').text()).toBe('The model is faster and cheaper.')
    expect(wrapper.text()).toContain('Özet hazırlanıyor')
  })
})
