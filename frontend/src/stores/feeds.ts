import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api } from '@/api/client'
import { useSettingsStore } from '@/stores/settings'
import type { Feed, FeedCreate, FeedRefreshResult, FeedUpdate } from '@/types/api'
import { errorMessage } from '@/utils/errors'

function byName(a: Feed, b: Feed): number {
  return a.name.localeCompare(b.name, 'tr')
}

export const useFeedsStore = defineStore('feeds', () => {
  const settings = useSettingsStore()

  const feeds = ref<Feed[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchFeeds(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      feeds.value = await api.listFeeds()
    } catch (e) {
      error.value = errorMessage(e)
    } finally {
      loading.value = false
    }
  }

  // Write actions throw on failure, so the calling view can show the error next to the
  // action that caused it. Turn the error into text with errorMessage().

  async function createFeed(body: FeedCreate): Promise<Feed> {
    const feed = await api.createFeed(body, settings.adminKey)
    feeds.value = [...feeds.value, feed].sort(byName)
    return feed
  }

  async function updateFeed(id: number, body: FeedUpdate): Promise<void> {
    const updated = await api.updateFeed(id, body, settings.adminKey)
    feeds.value = feeds.value.map((f) => (f.id === id ? updated : f)).sort(byName)
  }

  async function deleteFeed(id: number): Promise<void> {
    await api.deleteFeed(id, settings.adminKey)
    feeds.value = feeds.value.filter((f) => f.id !== id)
  }

  async function refreshFeed(id: number): Promise<FeedRefreshResult> {
    const result = await api.refreshFeed(id, settings.adminKey)
    await fetchFeeds() // article counts and last fetch time changed
    return result
  }

  return { feeds, loading, error, fetchFeeds, createFeed, updateFeed, deleteFeed, refreshFeed }
})
