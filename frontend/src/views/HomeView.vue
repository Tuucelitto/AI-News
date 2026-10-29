<script setup lang="ts">
import { onMounted } from 'vue'

import { useArticlesStore } from '@/stores/articles'

// Placeholder until step 9b: proves the frontend → Vite proxy → FastAPI wiring works.
const articles = useArticlesStore()

onMounted(() => articles.fetchArticles({ since_hours: 24 }))
</script>

<template>
  <h1 class="mb-4 text-2xl font-semibold">Son 24 saat</h1>
  <p v-if="articles.loading">Yükleniyor…</p>
  <p v-else-if="articles.error" class="text-red-700">Haberler yüklenemedi: {{ articles.error }}</p>
  <p v-else-if="articles.page">{{ articles.page.total }} haber bulundu.</p>
</template>
