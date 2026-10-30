import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

import { api } from '@/api/client'
import type { ArticleListItem } from '@/types/api'
import { errorMessage } from '@/utils/errors'
import { readStorage, writeStorage } from '@/utils/storage'

const FAVORITES_STORAGE = 'ai-news:favorites'
export const FAVORITES_PAGE_SIZE = 20

function loadIds(): number[] {
  try {
    const stored: unknown = JSON.parse(readStorage(FAVORITES_STORAGE) ?? '[]')
    return Array.isArray(stored) ? stored.filter(Number.isInteger) : []
  } catch {
    return [] // damaged value: start over instead of breaking the page
  }
}

// Favorites live in this browser only: there are no user accounts.
export const useFavoritesStore = defineStore('favorites', () => {
  const ids = ref<number[]>(loadIds()) // most recently added first
  watch(ids, (value) => writeStorage(FAVORITES_STORAGE, value.length ? JSON.stringify(value) : ''))

  const total = computed(() => ids.value.length)

  function isFavorite(id: number): boolean {
    return ids.value.includes(id)
  }

  function toggle(id: number): void {
    ids.value = isFavorite(id) ? ids.value.filter((i) => i !== id) : [id, ...ids.value]
  }

  const articles = ref<ArticleListItem[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchPage(page: number): Promise<void> {
    const start = (page - 1) * FAVORITES_PAGE_SIZE
    const wanted = ids.value.slice(start, start + FAVORITES_PAGE_SIZE)
    error.value = null
    if (wanted.length === 0) {
      articles.value = []
      return
    }
    loading.value = true
    try {
      const result = await api.listArticles({
        ids: wanted.join(','),
        size: FAVORITES_PAGE_SIZE,
      })
      articles.value = result.items
      // Articles of a deleted feed are gone from the server; forget them here too.
      const found = new Set(result.items.map((a) => a.id))
      ids.value = ids.value.filter((id) => !wanted.includes(id) || found.has(id))
    } catch (e) {
      error.value = errorMessage(e)
    } finally {
      loading.value = false
    }
  }

  return { ids, total, isFavorite, toggle, articles, loading, error, fetchPage }
})
