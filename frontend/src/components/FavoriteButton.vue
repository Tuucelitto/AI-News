<script setup lang="ts">
import { computed } from 'vue'

import { useFavoritesStore } from '@/stores/favorites'

const props = defineProps<{ articleId: number; withLabel?: boolean }>()

const favorites = useFavoritesStore()
const active = computed(() => favorites.isFavorite(props.articleId))
const label = computed(() => (active.value ? 'Favorilerden çıkar' : 'Favorilere ekle'))
</script>

<template>
  <!-- `relative z-10` keeps it clickable above the card's full-size link. -->
  <button
    type="button"
    class="relative z-10 inline-flex items-center gap-1.5 transition-colors"
    :class="[
      withLabel ? 'btn' : 'rounded p-1',
      active
        ? 'text-accent dark:text-accent-bright'
        : 'text-stone-400 hover:text-accent dark:text-stone-500 dark:hover:text-accent-bright',
    ]"
    :aria-pressed="active"
    :aria-label="label"
    :title="label"
    @click="favorites.toggle(articleId)"
  >
    <svg
      class="h-4 w-4"
      viewBox="0 0 24 24"
      :fill="active ? 'currentColor' : 'none'"
      stroke="currentColor"
      stroke-width="2"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <path d="M12 3l2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9z" />
    </svg>
    <span v-if="withLabel">{{ active ? 'Favorilerde' : 'Favorilere ekle' }}</span>
  </button>
</template>
