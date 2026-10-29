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
    <button
      type="button"
      class="rounded-md border border-gray-300 bg-white px-3 py-1.5 enabled:hover:bg-gray-100 disabled:opacity-40"
      :disabled="page <= 1"
      @click="emit('update:page', page - 1)"
    >
      ← Önceki
    </button>
    <span class="text-gray-600">Sayfa {{ page }} / {{ pageCount }}</span>
    <button
      type="button"
      class="rounded-md border border-gray-300 bg-white px-3 py-1.5 enabled:hover:bg-gray-100 disabled:opacity-40"
      :disabled="page >= pageCount"
      @click="emit('update:page', page + 1)"
    >
      Sonraki →
    </button>
  </nav>
</template>
