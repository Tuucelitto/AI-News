<script setup lang="ts">
import { computed } from 'vue'

import { useSettingsStore, type Theme } from '@/stores/settings'

const settings = useSettingsStore()

const OPTIONS: { value: Theme; label: string }[] = [
  { value: 'system', label: 'Sistem' },
  { value: 'light', label: 'Açık' },
  { value: 'dark', label: 'Koyu' },
]

const selectedIndex = computed(() => OPTIONS.findIndex((o) => o.value === settings.theme))

// Radio group keyboard pattern: arrow keys move the selection.
function onKeydown(event: KeyboardEvent) {
  const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key]
  if (!step) return
  event.preventDefault()
  const next = OPTIONS[(selectedIndex.value + step + OPTIONS.length) % OPTIONS.length]!
  settings.setTheme(next.value)
  ;(event.currentTarget as HTMLElement)
    .querySelector<HTMLElement>(`[data-theme="${next.value}"]`)
    ?.focus()
}
</script>

<template>
  <!-- A segmented control: the highlight slides under the selected option. -->
  <div
    role="radiogroup"
    aria-label="Tema"
    class="relative flex rounded-full bg-stone-100 p-0.5 dark:bg-stone-800"
    @keydown="onKeydown"
  >
    <span
      aria-hidden="true"
      class="absolute top-0.5 left-0.5 h-7 w-8 rounded-full bg-white shadow-sm transition-transform duration-200 ease-out dark:bg-stone-600"
      :style="{ transform: `translateX(${selectedIndex * 100}%)` }"
    />
    <button
      v-for="option in OPTIONS"
      :key="option.value"
      type="button"
      role="radio"
      :data-theme="option.value"
      :aria-checked="settings.theme === option.value"
      :aria-label="option.label"
      :title="option.label"
      :tabindex="settings.theme === option.value ? 0 : -1"
      class="relative z-10 flex h-7 w-8 items-center justify-center rounded-full transition-colors"
      :class="
        settings.theme === option.value
          ? 'text-stone-900 dark:text-white'
          : 'text-stone-500 hover:text-stone-900 dark:text-stone-400 dark:hover:text-white'
      "
      @click="settings.setTheme(option.value)"
    >
      <!-- System: a monitor -->
      <svg
        v-if="option.value === 'system'"
        class="h-4 w-4"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <rect x="3" y="4" width="18" height="12" rx="2" />
        <path d="M8 20h8M12 16v4" />
      </svg>
      <!-- Light: a sun -->
      <svg
        v-else-if="option.value === 'light'"
        class="h-4 w-4"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="4" />
        <path
          d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"
        />
      </svg>
      <!-- Dark: a moon -->
      <svg
        v-else
        class="h-4 w-4"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
      </svg>
    </button>
  </div>
</template>
