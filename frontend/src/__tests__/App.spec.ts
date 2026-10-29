import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it } from 'vitest'
import { h } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '../App.vue'

// Stub pages, so this test checks the layout without loading real views or calling the API.
const stub = (text: string) => ({ render: () => h('p', text) })

describe('App', () => {
  it('renders the navigation and the current page', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: stub('home page') },
        { path: '/feeds', component: stub('feeds page') },
        { path: '/status', component: stub('status page') },
      ],
    })
    router.push('/feeds')
    await router.isReady()

    const wrapper = mount(App, { global: { plugins: [router, createPinia()] } })

    const links = wrapper.findAll('nav a').map((a) => a.text())
    expect(links).toEqual(['AI Haberleri', 'Haberler', 'Kaynaklar', 'Durum'])
    expect(wrapper.text()).toContain('feeds page')
  })
})
