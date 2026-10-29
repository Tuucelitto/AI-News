<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import StatusBadge from '@/components/StatusBadge.vue'
import type { ArticleListItem } from '@/types/api'
import { formatDate, formatRelative } from '@/utils/format'

const props = defineProps<{ article: ArticleListItem }>()

// Fall back to the original English text until the Turkish summary is ready.
const title = computed(() => props.article.title_tr ?? props.article.title)
const text = computed(() => props.article.summary_tr ?? props.article.rss_summary)
const textLang = computed(() => (props.article.summary_tr ? 'tr' : 'en'))
</script>

<template>
  <!-- `relative` + the link's `after:inset-0` make the whole card clickable. -->
  <article
    class="relative rounded-lg border border-gray-200 bg-white p-4 transition hover:border-gray-400"
  >
    <div class="mb-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-gray-500">
      <span class="font-medium text-gray-700">{{ article.feed_name }}</span>
      <template v-if="article.published_at">
        <span aria-hidden="true">·</span>
        <time :datetime="article.published_at" :title="formatDate(article.published_at)">
          {{ formatRelative(article.published_at) }}
        </time>
      </template>
      <StatusBadge :status="article.summary_status" />
    </div>

    <h2 class="text-lg leading-snug font-semibold" :lang="article.title_tr ? 'tr' : 'en'">
      <RouterLink
        :to="{ name: 'article', params: { id: article.id } }"
        class="after:absolute after:inset-0 hover:underline"
      >
        {{ title }}
      </RouterLink>
    </h2>

    <p v-if="text" class="mt-1 line-clamp-3 text-sm text-gray-700" :lang="textLang">
      {{ text }}
    </p>
  </article>
</template>
