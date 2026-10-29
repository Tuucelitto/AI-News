import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api } from '@/api/client'
import type { ArticleListItem, ArticleQuery, Page } from '@/types/api'

export const useArticlesStore = defineStore('articles', () => {
  const page = ref<Page<ArticleListItem> | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchArticles(query: ArticleQuery = {}): Promise<void> {
    loading.value = true
    error.value = null
    try {
      page.value = await api.listArticles(query)
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  return { page, loading, error, fetchArticles }
})
