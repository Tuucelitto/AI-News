<script setup lang="ts">
import { onMounted } from 'vue'

import AddFeedForm from '@/components/AddFeedForm.vue'
import AdminKeyPanel from '@/components/AdminKeyPanel.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FeedItem from '@/components/FeedItem.vue'
import { useFeedsStore } from '@/stores/feeds'
import { useSettingsStore } from '@/stores/settings'

const feeds = useFeedsStore()
const settings = useSettingsStore()

onMounted(() => feeds.fetchFeeds())
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <h1 class="mb-5 font-serif text-4xl font-medium">Kaynaklar</h1>

    <AdminKeyPanel />
    <AddFeedForm v-if="settings.hasAdminKey" />

    <ErrorMessage v-if="feeds.error" :message="feeds.error" @retry="feeds.fetchFeeds()" />

    <div v-else-if="feeds.loading && feeds.feeds.length === 0" class="space-y-3" aria-busy="true">
      <div
        v-for="i in 4"
        :key="i"
        class="h-24 animate-pulse rounded-md bg-stone-200 dark:bg-stone-800"
      />
    </div>

    <ul v-else class="space-y-3">
      <FeedItem v-for="feed in feeds.feeds" :key="feed.id" :feed="feed" />
    </ul>
  </div>
</template>
