import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it } from 'vitest'
import { h } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '../App.vue'

// Stub pages, so this test checks the layout without loading real views or calling the API.
const stub = (text: string) => ({ render: () => h('p', text) })

async function mountAt(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: stub('home page') },
      { path: '/articles/:id', name: 'article', component: stub('article page') },
      { path: '/feeds', name: 'feeds', component: stub('feeds page') },
      { path: '/status', name: 'status', component: stub('status page') },
    ],
  })
  router.push(path)
  await router.isReady()
  const wrapper = mount(App, { global: { plugins: [router, createPinia()] } })
  return { wrapper, router }
}

function activeLinks(wrapper: Awaited<ReturnType<typeof mountAt>>['wrapper']) {
  return wrapper.findAll('nav a[aria-current="page"]').map((a) => a.text())
}

describe('App', () => {
  it('renders the navigation and the current page', async () => {
    const { wrapper } = await mountAt('/feeds')

    const links = wrapper.findAll('nav a').map((a) => a.text())
    expect(links).toEqual(['AI Haberleri', 'Haberler', 'Kaynaklar', 'Durum'])
    expect(wrapper.text()).toContain('feeds page')
  })

  it('highlights only the link of the current page', async () => {
    const { wrapper, router } = await mountAt('/feeds')
    expect(activeLinks(wrapper)).toEqual(['Kaynaklar'])

    await router.push('/status')
    await flushPromises()
    expect(activeLinks(wrapper)).toEqual(['Durum'])
  })

  it('keeps "Haberler" highlighted on an article page', async () => {
    const { wrapper } = await mountAt('/articles/5')

    expect(activeLinks(wrapper)).toEqual(['Haberler'])
  })
})
