<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter, type LocationQueryRaw } from 'vue-router'

import ArticleCard from '@/components/ArticleCard.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import PaginationNav from '@/components/PaginationNav.vue'
import { useArticlesStore } from '@/stores/articles'
import { useFeedsStore } from '@/stores/feeds'

const PAGE_SIZE = 20
const SEARCH_DEBOUNCE_MS = 300
const RANGES = [
  { value: '24h', label: 'Son 24 saat', hours: 24 },
  { value: '48h', label: '48 saat', hours: 48 },
  { value: '7d', label: '7 gün', hours: 24 * 7 },
  { value: 'all', label: 'Tümü', hours: undefined },
] as const
type Range = (typeof RANGES)[number]['value']
const DEFAULT_RANGE: Range = '24h'

const route = useRoute()
const router = useRouter()
const articles = useArticlesStore()
const feeds = useFeedsStore()

// The URL is the single source of truth for filters: refresh, back button and
// shared links all show the same list.
const filters = computed(() => {
  const query = route.query
  return {
    range: RANGES.find((r) => r.value === query.range)?.value ?? DEFAULT_RANGE,
    feedId: Number(query.feed) || undefined,
    q: typeof query.q === 'string' && query.q ? query.q : undefined,
    page: Math.max(1, Number(query.page) || 1),
  }
})

function updateFilters(changes: { range?: Range; feed?: number; q?: string; page?: number }) {
  const next = { ...filters.value, ...changes, ...('page' in changes ? {} : { page: 1 }) }
  const query: LocationQueryRaw = {}
  // Defaults are left out to keep the URL short.
  if (next.range !== DEFAULT_RANGE) query.range = next.range
  const feed = 'feed' in changes ? changes.feed : next.feedId
  if (feed) query.feed = String(feed)
  if (next.q) query.q = next.q
  if (next.page > 1) query.page = String(next.page)
  router.replace({ query })
}

function load() {
  const f = filters.value
  articles.fetchArticles({
    page: f.page,
    size: PAGE_SIZE,
    feed_id: f.feedId,
    q: f.q,
    since_hours: RANGES.find((r) => r.value === f.range)?.hours,
  })
}

watch(
  filters,
  () => {
    // While navigating to an article, the route changes before this view unmounts;
    // don't reload the list with that route's (empty) query.
    if (route.name === 'home') load()
  },
  { immediate: true },
)

// Search box: local text, written to the URL once typing pauses (debounce).
const searchText = ref(filters.value.q ?? '')
let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(searchText, (text) => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    const q = text.trim()
    // The API needs at least 2 characters.
    if (q.length !== 1 && q !== (filters.value.q ?? '')) updateFilters({ q })
  }, SEARCH_DEBOUNCE_MS)
})
// Keep the box in sync when the URL changes from outside (back button).
watch(
  () => filters.value.q,
  (q) => {
    if ((q ?? '') !== searchText.value.trim()) searchText.value = q ?? ''
  },
)
onBeforeUnmount(() => clearTimeout(searchTimer))

onMounted(() => {
  if (feeds.feeds.length === 0) feeds.fetchFeeds()
})

function onFeedChange(event: Event) {
  updateFilters({ feed: Number((event.target as HTMLSelectElement).value) || undefined })
}

// The newest story leads the first page; the rest fill the grid below it.
const lead = computed(() => {
  const page = articles.page
  return page?.page === 1 ? page.items[0] : undefined
})
const grid = computed(() => articles.page?.items.slice(lead.value ? 1 : 0) ?? [])

function onPageChange(page: number) {
  updateFilters({ page })
  window.scrollTo({ top: 0 })
}
</script>

<template>
  <div class="mb-6 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
    <div
      class="flex flex-wrap items-center gap-x-5 gap-y-1"
      role="group"
      aria-label="Zaman aralığı"
    >
      <button
        v-for="range in RANGES"
        :key="range.value"
        type="button"
        class="border-b-2 py-0.5 text-sm transition-colors"
        :class="
          filters.range === range.value
            ? 'border-accent font-medium text-stone-900 dark:border-accent-bright dark:text-white'
            : 'border-transparent text-stone-500 hover:text-stone-900 dark:text-stone-400 dark:hover:text-white'
        "
        :aria-pressed="filters.range === range.value"
        @click="updateFilters({ range: range.value })"
      >
        {{ range.label }}
      </button>
      <p v-if="articles.page" class="text-sm text-stone-400 dark:text-stone-500" aria-live="polite">
        {{ articles.page.total }} haber
      </p>
    </div>

    <div class="flex flex-col gap-2 sm:flex-row lg:w-[28rem]">
      <input
        v-model="searchText"
        type="search"
        placeholder="Haberlerde ara…"
        aria-label="Haberlerde ara"
        class="input-field min-w-0 flex-1"
      />
      <select
        :value="filters.feedId ?? ''"
        aria-label="Kaynak"
        class="input-field sm:w-44"
        @change="onFeedChange"
      >
        <option value="">Tüm kaynaklar</option>
        <option v-for="feed in feeds.feeds" :key="feed.id" :value="feed.id">
          {{ feed.name }}
        </option>
      </select>
    </div>
  </div>

  <ErrorMessage v-if="articles.error" :message="articles.error" @retry="load" />

  <div v-else-if="articles.loading && !articles.page" aria-busy="true">
    <div class="mb-8 h-56 animate-pulse rounded-md bg-stone-200 dark:bg-stone-800" />
    <div class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      <div
        v-for="i in 6"
        :key="i"
        class="h-40 animate-pulse rounded-md bg-stone-200 dark:bg-stone-800"
      />
    </div>
  </div>

  <template v-else-if="articles.page">
    <p
      v-if="articles.page.items.length === 0"
      class="rounded-md border border-dashed border-stone-300 p-8 text-center text-stone-600 dark:border-stone-700 dark:text-stone-400"
    >
      Bu filtrelere uyan haber yok.
    </p>

    <!-- Dimmed while a new page loads, instead of flashing skeletons again. -->
    <div class="transition-opacity" :class="{ 'opacity-50': articles.loading }">
      <ArticleCard v-if="lead" :article="lead" lead class="mb-8" />
      <div class="grid gap-x-8 gap-y-6 md:grid-cols-2 lg:grid-cols-3">
        <ArticleCard v-for="article in grid" :key="article.id" :article="article" />
      </div>
    </div>

    <PaginationNav
      :page="articles.page.page"
      :size="articles.page.size"
      :total="articles.page.total"
      @update:page="onPageChange"
    />
  </template>
</template>
