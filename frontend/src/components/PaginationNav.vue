<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ page: number; size: number; total: number }>()
const emit = defineEmits<{ 'update:page': [page: number] }>()

const pageCount = computed(() => Math.max(1, Math.ceil(props.total / props.size)))
</script>

<template>
  <nav
    v-if="pageCount > 1"
    aria-label="Sayfalama"
    class="mt-6 flex items-center justify-between text-sm"
  >
    <button type="button" class="btn" :disabled="page <= 1" @click="emit('update:page', page - 1)">
      ← Önceki
    </button>
    <span class="text-gray-600 dark:text-gray-400">Sayfa {{ page }} / {{ pageCount }}</span>
    <button
      type="button"
      class="btn"
      :disabled="page >= pageCount"
      @click="emit('update:page', page + 1)"
    >
      Sonraki →
    </button>
  </nav>
</template>
