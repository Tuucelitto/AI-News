<script setup lang="ts">
import { ref } from 'vue'

import { useFeedsStore } from '@/stores/feeds'
import { useSettingsStore } from '@/stores/settings'
import type { Feed, FeedRefreshResult } from '@/types/api'
import { errorMessage } from '@/utils/errors'
import { formatDate, formatRelative } from '@/utils/format'

const props = defineProps<{ feed: Feed }>()

const feeds = useFeedsStore()
const settings = useSettingsStore()

const busy = ref(false)
const confirmingDelete = ref(false)
const message = ref<{ text: string; tone: 'ok' | 'error' } | null>(null)

function describeRefresh(result: FeedRefreshResult): string {
  if (result.error) return `Çekilemedi: ${result.error}`
  if (result.not_modified) return 'Kaynakta yeni bir şey yok.'
  return (
    `${result.new_articles} yeni haber` +
    (result.new_articles
      ? ` (${result.queued_for_summary} özet kuyruğunda, ${result.skipped} kısa).`
      : '.')
  )
}

// Runs an action with a busy state and shows its outcome below the feed.
async function run(action: () => Promise<string | null>) {
  busy.value = true
  message.value = null
  try {
    const text = await action()
    if (text) message.value = { text, tone: 'ok' }
  } catch (e) {
    message.value = { text: errorMessage(e), tone: 'error' }
  } finally {
    busy.value = false
  }
}

const refresh = () => run(async () => describeRefresh(await feeds.refreshFeed(props.feed.id)))
const toggleActive = () =>
  run(async () => {
    await feeds.updateFeed(props.feed.id, { is_active: !props.feed.is_active })
    return null
  })
const remove = () =>
  run(async () => {
    await feeds.deleteFeed(props.feed.id) // this component disappears on success
    return null
  })
</script>

<template>
  <li class="card p-4" :class="{ 'opacity-60': !feed.is_active }">
    <div class="flex flex-wrap items-start justify-between gap-2">
      <div class="min-w-0">
        <h3 class="font-semibold">
          {{ feed.name }}
          <span
            v-if="!feed.is_active"
            class="ml-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-400"
          >
            Pasif
          </span>
        </h3>
        <a
          :href="feed.url"
          target="_blank"
          rel="noopener noreferrer"
          class="block truncate text-xs text-gray-500 hover:underline dark:text-gray-400"
        >
          {{ feed.url }}
        </a>
        <p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
          {{ feed.article_count }} haber
          <template v-if="feed.last_fetched_at">
            · son çekme
            <time :datetime="feed.last_fetched_at" :title="formatDate(feed.last_fetched_at)">
              {{ formatRelative(feed.last_fetched_at) }}
            </time>
          </template>
        </p>
        <p v-if="feed.last_error" class="mt-1 text-sm text-red-700 dark:text-red-400">
          Son hata: {{ feed.last_error }}
        </p>
      </div>

      <div v-if="settings.hasAdminKey" class="flex flex-wrap gap-2">
        <template v-if="!confirmingDelete">
          <button type="button" class="btn" :disabled="busy" @click="refresh">Yenile</button>
          <button type="button" class="btn" :disabled="busy" @click="toggleActive">
            {{ feed.is_active ? 'Pasifleştir' : 'Aktifleştir' }}
          </button>
          <button
            type="button"
            class="btn text-red-700 dark:text-red-400"
            :disabled="busy"
            @click="confirmingDelete = true"
          >
            Sil
          </button>
        </template>
        <!-- Two-step delete instead of window.confirm(), which blocks the whole page. -->
        <template v-else>
          <span class="self-center text-sm">{{ feed.article_count }} haberiyle silinsin mi?</span>
          <button
            type="button"
            class="rounded-md bg-red-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-800 disabled:opacity-40"
            :disabled="busy"
            @click="remove"
          >
            Evet, sil
          </button>
          <button type="button" class="btn" :disabled="busy" @click="confirmingDelete = false">
            İptal
          </button>
        </template>
      </div>
    </div>

    <p
      v-if="message"
      class="mt-2 text-sm"
      :class="
        message.tone === 'ok'
          ? 'text-green-700 dark:text-green-400'
          : 'text-red-700 dark:text-red-400'
      "
      :role="message.tone === 'error' ? 'alert' : 'status'"
    >
      {{ message.text }}
    </p>
  </li>
</template>
