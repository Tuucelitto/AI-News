<script setup lang="ts">
import { RouterLink, RouterView, useRoute } from 'vue-router'

import ThemeToggle from '@/components/ThemeToggle.vue'

const route = useRoute()

const links = [
  // "Haberler" stays highlighted on an article page too.
  { to: '/', label: 'Haberler', routes: ['home', 'article'] },
  { to: '/feeds', label: 'Kaynaklar', routes: ['feeds'] },
  { to: '/status', label: 'Durum', routes: ['status'] },
]

// Computed here instead of Vue Router's active-class: adding an active color on top of
// the normal color would leave two conflicting Tailwind color classes on one element.
function isActive(link: (typeof links)[number]): boolean {
  return link.routes.includes(String(route.name))
}
</script>

<template>
  <div class="min-h-screen bg-gray-50 text-gray-900 dark:bg-gray-950 dark:text-gray-100">
    <header class="border-b border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
      <div class="mx-auto flex max-w-4xl items-center justify-between gap-4 px-4 py-3">
        <nav class="flex items-center gap-4 sm:gap-6">
          <!-- Muted like the inactive links, so only the current page stands out. -->
          <RouterLink
            to="/"
            class="font-semibold text-gray-500 transition-colors hover:text-gray-900 dark:text-gray-400 dark:hover:text-white"
          >
            AI Haberleri
          </RouterLink>
          <div class="flex gap-1 text-sm">
            <RouterLink
              v-for="link in links"
              :key="link.to"
              :to="link.to"
              class="rounded-md px-2.5 py-1 transition-colors"
              :class="
                isActive(link)
                  ? 'bg-gray-100 font-medium text-gray-900 dark:bg-gray-800 dark:text-white'
                  : 'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white'
              "
              :aria-current="isActive(link) ? 'page' : undefined"
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
