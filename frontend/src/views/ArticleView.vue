<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import ErrorMessage from '@/components/ErrorMessage.vue'
import FavoriteButton from '@/components/FavoriteButton.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useArticlesStore } from '@/stores/articles'
import { useSettingsStore } from '@/stores/settings'
import { errorMessage } from '@/utils/errors'
import { formatDate } from '@/utils/format'
import { statusInfo } from '@/utils/status'

const props = defineProps<{ id: number }>()

const router = useRouter()
const store = useArticlesStore()
const settings = useSettingsStore()

watch(
  () => props.id,
  (id) => store.fetchArticle(id),
  { immediate: true },
)

// Only show the article that matches the URL, never a previous one.
const article = computed(() => (store.article?.id === props.id ? store.article : null))
const status = computed(() => (article.value ? statusInfo(article.value.summary_status) : null))

function goBack() {
  // Going back in history keeps the list's filters and page; fall back to the home page
  // when the article was opened directly (e.g. from a shared link).
  if (window.history.state?.back) router.back()
  else router.push({ name: 'home' })
}

// "Summarize again", e.g. when the fallback model got the meaning wrong.
const RESUMMARIZABLE = ['done', 'failed', 'skipped']
const canResummarize = computed(
  () =>
    settings.hasAdminKey &&
    article.value !== null &&
    RESUMMARIZABLE.includes(article.value.summary_status),
)
const resummarizing = ref(false)
const resummarizeMessage = ref<{ text: string; tone: 'ok' | 'error' } | null>(null)

async function resummarize() {
  resummarizing.value = true
  resummarizeMessage.value = null
  try {
    await store.resummarize(props.id)
    resummarizeMessage.value = {
      text: 'Metin yeniden alındı ve kuyruğa eklendi. Yeni özet birkaç dakika içinde hazır olur.',
      tone: 'ok',
    }
  } catch (e) {
    resummarizeMessage.value = { text: errorMessage(e), tone: 'error' }
  } finally {
    resummarizing.value = false
  }
}
</script>

<template>
  <div class="mx-auto max-w-2xl">
    <button
      type="button"
      class="mb-6 text-sm text-stone-500 transition-colors hover:text-stone-900 dark:text-stone-400 dark:hover:text-stone-100"
      @click="goBack"
    >
      ← Haberlere dön
    </button>

    <div v-if="store.articleNotFound" class="card p-8">
      <h1 class="font-serif text-2xl font-medium">Haber bulunamadı</h1>
      <p class="mt-1 text-stone-600 dark:text-stone-400">
        Bu haber silinmiş ya da hiç var olmamış olabilir.
      </p>
    </div>

    <ErrorMessage
      v-else-if="store.articleError"
      :message="store.articleError"
      @retry="store.fetchArticle(id)"
    />

    <div v-else-if="!article" class="space-y-3" aria-busy="true">
      <div class="h-8 w-3/4 animate-pulse rounded bg-stone-200 dark:bg-stone-800" />
      <div class="h-40 animate-pulse rounded bg-stone-200 dark:bg-stone-800" />
    </div>

    <article v-else>
      <div
        class="mb-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-stone-500 dark:text-stone-400"
      >
        <span class="eyebrow text-sm">{{ article.feed_name }}</span>
        <template v-if="article.published_at">
          <span aria-hidden="true">·</span>
          <time :datetime="article.published_at">{{ formatDate(article.published_at) }}</time>
        </template>
        <span v-if="article.author">· {{ article.author }}</span>
        <StatusBadge :status="article.summary_status" />
      </div>

      <h1
        class="font-serif text-4xl leading-[1.12] font-medium sm:text-5xl"
        :lang="article.title_tr ? 'tr' : 'en'"
      >
        {{ article.title_tr ?? article.title }}
      </h1>
      <p v-if="article.title_tr" class="mt-3 text-sm text-stone-500 dark:text-stone-400" lang="en">
        {{ article.title }}
      </p>

      <template v-if="article.summary_tr">
        <p
          class="mt-6 border-t border-stone-300 pt-6 font-serif text-xl leading-relaxed text-stone-800 dark:border-stone-700 dark:text-stone-200"
        >
          {{ article.summary_tr }}
        </p>

        <section
          v-if="article.key_points?.length"
          class="mt-8 border-l-2 border-accent pl-5 dark:border-accent-bright"
        >
          <h2 class="mb-2 font-serif text-xl font-medium">Öne çıkanlar</h2>
          <ul class="list-disc space-y-1.5 pl-5 leading-relaxed text-stone-800 dark:text-stone-200">
            <li v-for="(point, index) in article.key_points" :key="index">{{ point }}</li>
          </ul>
        </section>
      </template>

      <template v-else>
        <p v-if="status" class="mt-5 text-sm text-stone-500 italic dark:text-stone-400">
          {{ status.description }}
        </p>
        <p
          v-if="article.rss_summary"
          class="mt-2 leading-relaxed text-stone-800 dark:text-stone-200"
          lang="en"
        >
          {{ article.rss_summary }}
        </p>
      </template>

      <div class="mt-8 flex flex-wrap items-center gap-3">
        <a
          :href="article.url"
          target="_blank"
          rel="noopener noreferrer"
          class="btn-primary inline-block px-4 py-2"
        >
          Orijinal habere git ↗
        </a>
        <FavoriteButton :article-id="article.id" with-label />
        <button
          v-if="canResummarize"
          type="button"
          class="btn"
          :disabled="resummarizing"
          @click="resummarize"
        >
          {{ resummarizing ? 'Ekleniyor…' : 'Yeniden özetle' }}
        </button>
      </div>
      <p
        v-if="resummarizeMessage"
        class="mt-2 text-sm"
        :class="
          resummarizeMessage.tone === 'ok'
            ? 'text-green-700 dark:text-green-400'
            : 'text-red-700 dark:text-red-400'
        "
        :role="resummarizeMessage.tone === 'error' ? 'alert' : 'status'"
      >
        {{ resummarizeMessage.text }}
      </p>

      <p
        v-if="article.model_used && article.summarized_at"
        class="mt-6 text-xs text-stone-400 dark:text-stone-500"
      >
        Özet {{ article.model_used }} ile {{ formatDate(article.summarized_at) }} tarihinde
        oluşturuldu.
      </p>
    </article>
  </div>
</template>
