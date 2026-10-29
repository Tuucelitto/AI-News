<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'

const links = [
  { to: '/', label: 'Haberler' },
  { to: '/feeds', label: 'Kaynaklar' },
  { to: '/status', label: 'Durum' },
]
</script>

<template>
  <div class="min-h-screen bg-gray-50 text-gray-900">
    <header class="border-b border-gray-200 bg-white">
      <nav class="mx-auto flex max-w-4xl items-center gap-6 px-4 py-3">
        <RouterLink to="/" class="font-semibold">AI Haberleri</RouterLink>
        <div class="flex gap-4 text-sm">
          <RouterLink
            v-for="link in links"
            :key="link.to"
            :to="link.to"
            class="text-gray-600 hover:text-gray-900"
            exact-active-class="font-medium text-gray-900"
          >
            {{ link.label }}
          </RouterLink>
        </div>
      </nav>
    </header>

    <main class="mx-auto max-w-4xl px-4 py-6">
      <RouterView />
    </main>
  </div>
</template>
