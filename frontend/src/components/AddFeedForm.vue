<script setup lang="ts">
import { ref } from 'vue'

import { useFeedsStore } from '@/stores/feeds'
import { errorMessage } from '@/utils/errors'

const feeds = useFeedsStore()

const url = ref('')
const name = ref('')
const saving = ref(false)
const error = ref<string | null>(null)
const added = ref<string | null>(null)

async function submit() {
  saving.value = true
  error.value = null
  added.value = null
  try {
    // The backend downloads the URL to check that it really is a feed.
    const feed = await feeds.createFeed({
      url: url.value.trim(),
      name: name.value.trim() || undefined,
    })
    added.value = feed.name
    url.value = ''
    name.value = ''
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <form class="card mb-6 space-y-2 p-4" @submit.prevent="submit">
    <h2 class="font-serif text-xl font-medium">Kaynak ekle</h2>
    <div class="flex flex-col gap-2 sm:flex-row">
      <input
        v-model="url"
        type="url"
        required
        placeholder="https://site.com/feed.xml"
        aria-label="RSS adresi"
        class="input-field flex-[2]"
      />
      <input
        v-model="name"
        type="text"
        maxlength="100"
        placeholder="Ad (isteğe bağlı)"
        aria-label="Kaynak adı"
        class="input-field flex-1"
      />
      <button type="submit" class="btn-primary" :disabled="saving || !url.trim()">
        {{ saving ? 'Kontrol ediliyor…' : 'Ekle' }}
      </button>
    </div>
    <p v-if="error" role="alert" class="text-sm text-red-700 dark:text-red-400">{{ error }}</p>
    <p v-if="added" class="text-sm text-green-700 dark:text-green-400">
      “{{ added }}” eklendi. Haberleri bir sonraki çekmede (en geç bir saat içinde) ya da “Yenile”
      ile hemen gelir.
    </p>
  </form>
</template>
