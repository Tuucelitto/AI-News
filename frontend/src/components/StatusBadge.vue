<script setup lang="ts">
import { computed } from 'vue'

import type { SummaryStatus } from '@/types/api'
import { statusInfo } from '@/utils/status'

const props = defineProps<{ status: SummaryStatus }>()

const info = computed(() => statusInfo(props.status))

const toneClasses = {
  waiting: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
  muted: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
  error: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
}
</script>

<template>
  <span
    v-if="info"
    class="rounded-full px-2 py-0.5 text-xs font-medium"
    :class="toneClasses[info.tone]"
  >
    {{ info.label }}
  </span>
</template>
