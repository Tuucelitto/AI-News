import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api } from '@/api/client'
import type { Feed } from '@/types/api'

export const useFeedsStore = defineStore('feeds', () => {
  const feeds = ref<Feed[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchFeeds(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      feeds.value = await api.listFeeds()
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  return { feeds, loading, error, fetchFeeds }
})
