import { createMemoryHistory, createRouter } from 'vue-router'

import { routes } from '@/router'
import type { ArticleDetail, ArticleListItem } from '@/types/api'

/** The app's real routes, with in-memory history instead of the browser URL bar. */
export function testRouter() {
  return createRouter({ history: createMemoryHistory(), routes })
}

export function makeArticle(overrides: Partial<ArticleDetail> = {}): ArticleDetail {
  return {
    id: 1,
    feed_id: 1,
    feed_name: 'OpenAI',
    title: 'A new model',
    url: 'https://openai.example.com/model',
    published_at: new Date(Date.now() - 2 * 3600 * 1000).toISOString(),
    title_tr: 'Yeni bir model',
    summary_tr: 'Model daha hızlı ve daha ucuz.',
    rss_summary: 'The model is faster and cheaper.',
    summary_status: 'done',
    author: null,
    key_points: ['Daha hızlı', 'Daha ucuz'],
    model_used: 'gemini-3.8-flash',
    summarized_at: new Date().toISOString(),
    ...overrides,
  }
}

export function makeListItem(overrides: Partial<ArticleListItem> = {}): ArticleListItem {
  const { author, key_points, model_used, summarized_at, ...item } = makeArticle(overrides)
  void [author, key_points, model_used, summarized_at] // detail-only fields, dropped
  return item
}
