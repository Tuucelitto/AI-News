import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api } from '@/api/client'
import type { QueueStatus } from '@/types/api'

export const useQueueStore = defineStore('queue', () => {
  const status = ref<QueueStatus | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchStatus(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      status.value = await api.queueStatus()
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  return { status, loading, error, fetchStatus }
})
