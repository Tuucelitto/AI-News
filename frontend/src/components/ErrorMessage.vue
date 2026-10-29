<script setup lang="ts">
defineProps<{ message: string }>()
defineEmits<{ retry: [] }>()
</script>

<template>
  <div
    role="alert"
    class="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-300"
  >
    <p class="font-medium">Bir sorun oluştu.</p>
    <p class="mt-1 text-red-700 dark:text-red-400">{{ message }}</p>
    <button
      type="button"
      class="mt-3 rounded-md bg-red-700 px-3 py-1.5 text-white hover:bg-red-800"
      @click="$emit('retry')"
    >
      Tekrar dene
    </button>
  </div>
</template>
