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
  <h1 class="mb-4 text-2xl font-semibold">Kaynaklar</h1>

  <AdminKeyPanel />
  <AddFeedForm v-if="settings.hasAdminKey" />

  <ErrorMessage v-if="feeds.error" :message="feeds.error" @retry="feeds.fetchFeeds()" />

  <div v-else-if="feeds.loading && feeds.feeds.length === 0" class="space-y-3" aria-busy="true">
    <div
      v-for="i in 4"
      :key="i"
      class="h-24 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800"
    />
  </div>

  <ul v-else class="space-y-3">
    <FeedItem v-for="feed in feeds.feeds" :key="feed.id" :feed="feed" />
  </ul>
</template>
