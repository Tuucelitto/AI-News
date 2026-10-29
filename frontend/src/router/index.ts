import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

// Views are lazy-loaded: each page's code is downloaded only when it is first opened.
export const routes: RouteRecordRaw[] = [
  { path: '/', name: 'home', component: () => import('@/views/HomeView.vue') },
  {
    path: '/articles/:id(\\d+)', // digits only; anything else falls through to not-found
    name: 'article',
    component: () => import('@/views/ArticleView.vue'),
    props: (route) => ({ id: Number(route.params.id) }),
  },
  { path: '/feeds', name: 'feeds', component: () => import('@/views/FeedsView.vue') },
  { path: '/status', name: 'status', component: () => import('@/views/StatusView.vue') },
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

export default router
