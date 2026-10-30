import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import { useSettingsStore } from '@/stores/settings'

// Views are lazy-loaded: each page's code is downloaded only when it is first opened.
export const routes: RouteRecordRaw[] = [
  { path: '/', name: 'home', component: () => import('@/views/HomeView.vue') },
  {
    path: '/articles/:id(\\d+)', // digits only; anything else falls through to not-found
    name: 'article',
    component: () => import('@/views/ArticleView.vue'),
    props: (route) => ({ id: Number(route.params.id) }),
  },
  { path: '/favoriler', name: 'favorites', component: () => import('@/views/FavoritesView.vue') },
  { path: '/feeds', name: 'feeds', component: () => import('@/views/FeedsView.vue') },
  {
    path: '/status',
    name: 'status',
    component: () => import('@/views/StatusView.vue'),
    meta: { requiresAdmin: true },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

// Hides admin pages from visitors; the API rejects them too, this only avoids a broken page.
router.beforeEach((to) => {
  if (to.meta.requiresAdmin && !useSettingsStore().hasAdminKey) return { name: 'home' }
})

export default router
