<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'

import ThemeToggle from '@/components/ThemeToggle.vue'

const links = [
  { to: '/', label: 'Haberler' },
  { to: '/feeds', label: 'Kaynaklar' },
  { to: '/status', label: 'Durum' },
]
</script>

<template>
  <div class="min-h-screen bg-gray-50 text-gray-900 dark:bg-gray-950 dark:text-gray-100">
    <header class="border-b border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
      <div class="mx-auto flex max-w-4xl items-center justify-between gap-4 px-4 py-3">
        <nav class="flex items-center gap-6">
          <RouterLink to="/" class="font-semibold">AI Haberleri</RouterLink>
          <div class="flex gap-4 text-sm">
            <RouterLink
              v-for="link in links"
              :key="link.to"
              :to="link.to"
              class="text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
              exact-active-class="font-medium text-gray-900 dark:text-gray-100"
            >
              {{ link.label }}
            </RouterLink>
          </div>
        </nav>
        <ThemeToggle />
      </div>
    </header>

    <main class="mx-auto max-w-4xl px-4 py-6">
      <RouterView />
    </main>
  </div>
</template>
