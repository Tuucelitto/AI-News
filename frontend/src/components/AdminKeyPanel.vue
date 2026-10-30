<script setup lang="ts">
import { ref } from 'vue'

import { useSettingsStore } from '@/stores/settings'

const settings = useSettingsStore()

const keyInput = ref('')
const checking = ref(false)
const error = ref<string | null>(null)

async function save() {
  checking.value = true
  error.value = await settings.saveAdminKey(keyInput.value.trim())
  checking.value = false
  if (!error.value) keyInput.value = ''
}
</script>

<template>
  <section class="card mb-6 p-4 text-sm" aria-label="Yönetici anahtarı">
    <div v-if="settings.hasAdminKey" class="flex flex-wrap items-center justify-between gap-2">
      <p class="text-green-700 dark:text-green-400">
        ✓ Yönetici modu açık: değişiklik yapabilirsin.
      </p>
      <button type="button" class="btn" @click="settings.forgetAdminKey()">Anahtarı unut</button>
    </div>

    <form v-else class="space-y-2" @submit.prevent="save">
      <p class="text-stone-600 dark:text-stone-400">
        Değişiklik yapmak için yönetici anahtarını giriniz.
      </p>
      <div class="flex gap-2">
        <input
          v-model="keyInput"
          type="password"
          autocomplete="off"
          placeholder="Yönetici anahtarı"
          aria-label="Yönetici anahtarı"
          class="input-field flex-1"
        />
        <button type="submit" class="btn-primary" :disabled="!keyInput.trim() || checking">
          {{ checking ? 'Kontrol ediliyor…' : 'Kaydet' }}
        </button>
      </div>
      <p v-if="error" role="alert" class="text-red-700 dark:text-red-400">{{ error }}</p>
    </form>
  </section>
</template>
