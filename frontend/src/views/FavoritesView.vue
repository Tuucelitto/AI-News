<script setup lang="ts">
import { ref, watch } from 'vue'

import ArticleCard from '@/components/ArticleCard.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import PaginationNav from '@/components/PaginationNav.vue'
import { FAVORITES_PAGE_SIZE, useFavoritesStore } from '@/stores/favorites'

const favorites = useFavoritesStore()
const page = ref(1)

watch(page, (value) => favorites.fetchPage(value), { immediate: true })

function onPageChange(value: number) {
  page.value = value
  window.scrollTo({ top: 0 })
}
</script>

<template>
  <h1 class="mb-1 font-serif text-4xl font-medium">Favoriler</h1>
  <p class="mb-6 text-sm text-stone-500 dark:text-stone-400">
    Favorilerin yalnızca bu tarayıcıda saklanır.
  </p>

  <ErrorMessage
    v-if="favorites.error"
    :message="favorites.error"
    @retry="favorites.fetchPage(page)"
  />

  <p
    v-else-if="favorites.total === 0"
    class="rounded-md border border-dashed border-stone-300 p-8 text-center text-stone-600 dark:border-stone-700 dark:text-stone-400"
  >
    Henüz favori haberin yok. Beğendiğin haberlerdeki yıldıza dokun.
  </p>

  <template v-else>
    <div
      class="grid gap-x-8 gap-y-6 transition-opacity md:grid-cols-2 lg:grid-cols-3"
      :class="{ 'opacity-50': favorites.loading }"
    >
      <ArticleCard v-for="article in favorites.articles" :key="article.id" :article="article" />
    </div>

    <PaginationNav
      :page="page"
      :size="FAVORITES_PAGE_SIZE"
      :total="favorites.total"
      @update:page="onPageChange"
    />
  </template>
</template>
