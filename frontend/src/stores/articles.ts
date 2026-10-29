import { defineStore } from 'pinia'
import { ref } from 'vue'

import { ApiError, api } from '@/api/client'
import type { ArticleDetail, ArticleListItem, ArticleQuery, Page } from '@/types/api'

function messageOf(e: unknown): string {
  return e instanceof Error ? e.message : String(e)
}

export const useArticlesStore = defineStore('articles', () => {
  // --- List ---
  const page = ref<Page<ArticleListItem> | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  // When filters change quickly, an older response may arrive after a newer one.
  // Only the latest request is allowed to update the state.
  let latestListRequest = 0

  async function fetchArticles(query: ArticleQuery = {}): Promise<void> {
    const requestId = ++latestListRequest
    loading.value = true
    error.value = null
    try {
      const result = await api.listArticles(query)
      if (requestId === latestListRequest) page.value = result
    } catch (e) {
      if (requestId === latestListRequest) error.value = messageOf(e)
    } finally {
      if (requestId === latestListRequest) loading.value = false
    }
  }

  // --- Detail ---
  const article = ref<ArticleDetail | null>(null)
  const articleLoading = ref(false)
  const articleError = ref<string | null>(null)
  const articleNotFound = ref(false)

  async function fetchArticle(id: number): Promise<void> {
    articleLoading.value = true
    articleError.value = null
    articleNotFound.value = false
    if (article.value?.id !== id) article.value = null // don't flash the previous article
    try {
      article.value = await api.getArticle(id)
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) articleNotFound.value = true
      else articleError.value = messageOf(e)
    } finally {
      articleLoading.value = false
    }
  }

  return {
    page,
    loading,
    error,
    fetchArticles,
    article,
    articleLoading,
    articleError,
    articleNotFound,
    fetchArticle,
  }
})
