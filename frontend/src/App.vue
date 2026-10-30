<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

import ThemeToggle from '@/components/ThemeToggle.vue'
import { useSettingsStore } from '@/stores/settings'
import { formatToday } from '@/utils/format'

const route = useRoute()
const settings = useSettingsStore()
const today = formatToday()

const links = [
  // "Haberler" stays highlighted on an article page too.
  { to: '/', label: 'Haberler', routes: ['home', 'article'] },
  { to: '/favoriler', label: 'Favoriler', routes: ['favorites'] },
  { to: '/feeds', label: 'Kaynaklar', routes: ['feeds'] },
]
// Only the owner sees the status dashboard.
const visibleLinks = computed(() =>
  settings.hasAdminKey ? [...links, { to: '/status', label: 'Durum', routes: ['status'] }] : links,
)

// Computed here instead of Vue Router's active-class: adding an active color on top of
// the normal color would leave two conflicting Tailwind color classes on one element.
function isActive(link: (typeof links)[number]): boolean {
  return link.routes.includes(String(route.name))
}
</script>

<template>
  <div
    class="flex min-h-screen flex-col bg-paper text-stone-900 dark:bg-stone-950 dark:text-stone-100"
  >
    <header class="mx-auto w-full max-w-6xl px-4 pt-5 sm:px-6">
      <div
        class="flex items-center justify-between gap-4 border-b-2 border-stone-900 pb-3 dark:border-stone-100"
      >
        <nav class="flex flex-wrap items-baseline gap-x-8 gap-y-1">
          <RouterLink
            to="/"
            class="font-serif text-3xl font-semibold tracking-tight transition-colors hover:text-accent dark:hover:text-accent-bright"
          >
            AI Haberleri
          </RouterLink>
          <div class="flex gap-5 text-sm">
            <RouterLink
              v-for="link in visibleLinks"
              :key="link.to"
              :to="link.to"
              class="border-b-2 py-0.5 transition-colors"
              :class="
                isActive(link)
                  ? 'border-accent font-medium text-stone-900 dark:border-accent-bright dark:text-white'
                  : 'border-transparent text-stone-500 hover:text-stone-900 dark:text-stone-400 dark:hover:text-white'
              "
              :aria-current="isActive(link) ? 'page' : undefined"
            >
              {{ link.label }}
            </RouterLink>
          </div>
        </nav>
        <div class="flex shrink-0 items-center gap-4">
          <p class="hidden text-sm text-stone-500 md:block dark:text-stone-400">{{ today }}</p>
          <ThemeToggle />
        </div>
      </div>
    </header>

    <main class="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6">
      <RouterView />
    </main>

    <footer class="mx-auto w-full max-w-6xl px-4 pb-6 sm:px-6">
      <p
        class="border-t border-stone-300 pt-3 text-xs text-stone-500 dark:border-stone-700 dark:text-stone-400"
      >
        Özetler yapay zekâ ile oluşturulur ve hata içerebilir.
      </p>
    </footer>
  </div>
</template>
