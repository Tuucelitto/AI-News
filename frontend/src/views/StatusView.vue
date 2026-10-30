<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink } from 'vue-router'

import { usePolling } from '@/composables/usePolling'
import { useArticlesStore } from '@/stores/articles'
import { useQueueStore } from '@/stores/queue'
import { useSettingsStore } from '@/stores/settings'
import type { ModelStatus, SummaryStatus } from '@/types/api'
import { errorMessage } from '@/utils/errors'
import { formatDate, formatRelative } from '@/utils/format'

const POLL_INTERVAL_MS = 15_000

const queue = useQueueStore()
const articles = useArticlesStore()
const settings = useSettingsStore()

usePolling(() => queue.fetchStatus(), POLL_INTERVAL_MS)

const COUNT_LABELS: [SummaryStatus, string][] = [
  ['pending', 'Kuyrukta'],
  ['processing', 'İşleniyor'],
  ['done', 'Özetlendi'],
  ['skipped', 'Kısa (atlandı)'],
  ['failed', 'Başarısız'],
  ['new', 'Metin bekliyor'],
]

function usagePercent(model: ModelStatus): number {
  return Math.min(100, Math.round((model.requests_today / model.daily_limit) * 100))
}

function isPaused(model: ModelStatus): boolean {
  return model.paused_until !== null && new Date(model.paused_until) > new Date()
}

// Per-article state for the "try again" buttons.
const retrying = ref<number | null>(null)
const retryError = ref<{ id: number; text: string } | null>(null)

async function retry(id: number) {
  retrying.value = id
  retryError.value = null
  try {
    await articles.resummarize(id)
    await queue.fetchStatus()
  } catch (e) {
    retryError.value = { id, text: errorMessage(e) }
  } finally {
    retrying.value = null
  }
}
</script>

<template>
  <div class="mx-auto max-w-4xl">
    <h1 class="mb-5 font-serif text-4xl font-medium">Durum</h1>

    <p
      v-if="queue.error"
      role="alert"
      class="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-300"
    >
      Durum güncellenemedi: {{ queue.error }}
    </p>

    <div v-if="!queue.status && !queue.error" class="space-y-3" aria-busy="true">
      <div
        v-for="i in 3"
        :key="i"
        class="h-24 animate-pulse rounded-md bg-stone-200 dark:bg-stone-800"
      />
    </div>

    <template v-if="queue.status">
      <section aria-labelledby="counts-title" class="mb-8">
        <h2 id="counts-title" class="section-title">Haberler</h2>
        <dl class="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <div v-for="[status, label] in COUNT_LABELS" :key="status" class="card p-3">
            <dt class="text-xs text-stone-500 dark:text-stone-400">{{ label }}</dt>
            <dd
              class="font-serif text-3xl font-medium"
              :class="{
                'text-red-700 dark:text-red-400':
                  status === 'failed' && queue.status.counts.failed > 0,
              }"
            >
              {{ queue.status.counts[status] }}
            </dd>
          </div>
        </dl>
      </section>

      <section aria-labelledby="models-title" class="mb-8">
        <h2 id="models-title" class="section-title">Gemini kotası (bugün)</h2>
        <div class="grid gap-3 sm:grid-cols-2">
          <div v-for="model in queue.status.models" :key="model.model" class="card p-4">
            <div class="flex items-baseline justify-between gap-2">
              <p class="font-medium">{{ model.model }}</p>
              <p class="text-xs text-stone-500 dark:text-stone-400">
                {{ model.role === 'primary' ? 'Ana model' : 'Yedek model' }}
              </p>
            </div>
            <div
              class="mt-3 h-2 overflow-hidden rounded-full bg-stone-200 dark:bg-stone-800"
              role="progressbar"
              :aria-valuenow="model.requests_today"
              aria-valuemin="0"
              :aria-valuemax="model.daily_limit"
              :aria-label="`${model.model} günlük kota kullanımı`"
            >
              <div
                class="h-full rounded-full"
                :class="
                  usagePercent(model) >= 100 ? 'bg-red-600' : 'bg-accent dark:bg-accent-bright'
                "
                :style="{ width: `${usagePercent(model)}%` }"
              />
            </div>
            <p class="mt-2 text-sm">{{ model.requests_today }} / {{ model.daily_limit }} istek</p>
            <p v-if="isPaused(model)" class="mt-1 text-sm text-amber-700 dark:text-amber-400">
              Hata sonrası duraklatıldı, {{ formatRelative(model.paused_until!) }} devam edecek.
            </p>
            <p class="mt-1 text-xs text-stone-500 dark:text-stone-400">
              Kota {{ formatRelative(model.quota_resets_at) }} sıfırlanır.
            </p>
          </div>
        </div>
      </section>

      <section aria-labelledby="scheduler-title" class="mb-8">
        <h2 id="scheduler-title" class="section-title">Zamanlayıcı</h2>
        <div class="card space-y-1 p-4 text-sm">
          <p>
            <span
              class="mr-1 inline-block h-2 w-2 rounded-full"
              :class="queue.status.scheduler_running ? 'bg-green-600' : 'bg-stone-400'"
              aria-hidden="true"
            />
            {{ queue.status.scheduler_running ? 'Çalışıyor' : 'Kapalı' }}
          </p>
          <p v-if="queue.status.last_fetch_at" class="text-stone-600 dark:text-stone-400">
            Son RSS çekme:
            <time
              :datetime="queue.status.last_fetch_at"
              :title="formatDate(queue.status.last_fetch_at)"
            >
              {{ formatRelative(queue.status.last_fetch_at) }}
            </time>
          </p>
          <p v-if="queue.status.next_fetch_at" class="text-stone-600 dark:text-stone-400">
            Sıradaki çekme:
            <time
              :datetime="queue.status.next_fetch_at"
              :title="formatDate(queue.status.next_fetch_at)"
            >
              {{ formatRelative(queue.status.next_fetch_at) }}
            </time>
          </p>
        </div>
      </section>

      <section aria-labelledby="failed-title">
        <h2 id="failed-title" class="section-title">Özetlenemeyen haberler</h2>
        <p v-if="queue.failed.length === 0" class="text-sm text-stone-500 dark:text-stone-400">
          Özetlenemeyen haber yok.
        </p>
        <ul v-else class="space-y-2">
          <li v-for="article in queue.failed" :key="article.id" class="card p-3 text-sm">
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <RouterLink
                  :to="{ name: 'article', params: { id: article.id } }"
                  class="font-medium hover:underline"
                >
                  {{ article.title }}
                </RouterLink>
                <p class="text-xs text-stone-500 dark:text-stone-400">{{ article.feed_name }}</p>
              </div>
              <button
                v-if="settings.hasAdminKey"
                type="button"
                class="btn shrink-0"
                :disabled="retrying !== null"
                @click="retry(article.id)"
              >
                {{ retrying === article.id ? 'Ekleniyor…' : 'Tekrar özetle' }}
              </button>
            </div>
            <p
              v-if="retryError?.id === article.id"
              role="alert"
              class="mt-1 text-red-700 dark:text-red-400"
            >
              {{ retryError.text }}
            </p>
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>
