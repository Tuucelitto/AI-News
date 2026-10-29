<script setup lang="ts">
import { computed } from 'vue'

import { useSettingsStore } from '@/stores/settings'

const settings = useSettingsStore()

const LABELS = {
  system: { icon: '◐', text: 'Sistem' },
  light: { icon: '☀', text: 'Açık' },
  dark: { icon: '☾', text: 'Koyu' },
} as const

const current = computed(() => LABELS[settings.theme])
</script>

<template>
  <button
    type="button"
    class="btn flex items-center gap-1.5"
    :aria-label="`Tema: ${current.text}. Değiştirmek için tıkla.`"
    :title="`Tema: ${current.text}`"
    @click="settings.cycleTheme()"
  >
    <span aria-hidden="true">{{ current.icon }}</span>
    <span class="hidden sm:inline">{{ current.text }}</span>
  </button>
</template>
