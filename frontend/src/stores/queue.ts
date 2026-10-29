import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api } from '@/api/client'
import type { ArticleListItem, QueueStatus } from '@/types/api'
import { errorMessage } from '@/utils/errors'

export const useQueueStore = defineStore('queue', () => {
  const status = ref<QueueStatus | null>(null)
  const failed = ref<ArticleListItem[]>([])
  const error = ref<string | null>(null)

  /** Status and failed articles together; called repeatedly by the status page. */
  async function fetchStatus(): Promise<void> {
    try {
      const [queueStatus, failedPage] = await Promise.all([
        api.queueStatus(),
        api.listArticles({ status: 'failed', size: 50 }),
      ])
      status.value = queueStatus
      failed.value = failedPage.items
      error.value = null
    } catch (e) {
      // Keep showing the last known status; just report that refreshing failed.
      error.value = errorMessage(e)
    }
  }

  return { status, failed, error, fetchStatus }
})
