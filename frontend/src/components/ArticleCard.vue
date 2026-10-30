<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import FavoriteButton from '@/components/FavoriteButton.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import type { ArticleListItem } from '@/types/api'
import { formatDate, formatRelative } from '@/utils/format'

const props = defineProps<{ article: ArticleListItem; lead?: boolean }>()

// Fall back to the original English text until the Turkish summary is ready.
const title = computed(() => props.article.title_tr ?? props.article.title)
const text = computed(() => props.article.summary_tr ?? props.article.rss_summary)
const textLang = computed(() => (props.article.summary_tr ? 'tr' : 'en'))
</script>

<template>
  <!-- `relative` + the link's `after:inset-0` make the whole story clickable. -->
  <article
    class="group relative"
    :class="
      lead
        ? 'grid gap-x-10 gap-y-3 lg:grid-cols-5'
        : 'border-t border-stone-300 pt-3 dark:border-stone-700'
    "
  >
    <div :class="{ 'lg:col-span-3': lead }">
      <div
        class="mb-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-stone-500 dark:text-stone-400"
      >
        <span class="eyebrow">{{ article.feed_name }}</span>
        <template v-if="article.published_at">
          <span aria-hidden="true">·</span>
          <time :datetime="article.published_at" :title="formatDate(article.published_at)">
            {{ formatRelative(article.published_at) }}
          </time>
        </template>
        <StatusBadge :status="article.summary_status" />
        <FavoriteButton :article-id="article.id" class="ml-auto" />
      </div>

      <h2
        class="font-serif font-medium transition-colors group-hover:text-accent dark:group-hover:text-accent-bright"
        :class="lead ? 'text-4xl leading-[1.1] lg:text-5xl' : 'text-[1.4rem] leading-snug'"
        :lang="article.title_tr ? 'tr' : 'en'"
      >
        <RouterLink
          :to="{ name: 'article', params: { id: article.id } }"
          class="after:absolute after:inset-0"
        >
          {{ title }}
        </RouterLink>
      </h2>
    </div>

    <p
      v-if="text"
      class="leading-relaxed text-stone-700 dark:text-stone-300"
      :class="lead ? 'font-serif text-lg lg:col-span-2' : 'mt-1.5 line-clamp-4 text-sm'"
      :lang="textLang"
    >
      {{ text }}
    </p>
  </article>
</template>
