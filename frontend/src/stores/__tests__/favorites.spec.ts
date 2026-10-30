import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

import { makeListItem } from '@/__tests__/helpers'
import { api } from '@/api/client'
import { useFavoritesStore } from '@/stores/favorites'

const STORAGE_KEY = 'ai-news:favorites'

describe('favorites store', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  afterEach(() => vi.restoreAllMocks())

  it('adds and removes a favorite, newest first, and remembers them', async () => {
    const favorites = useFavoritesStore()

    favorites.toggle(1)
    favorites.toggle(2)
    await nextTick()
    expect(favorites.ids).toEqual([2, 1])
    expect(localStorage.getItem(STORAGE_KEY)).toBe('[2,1]')

    favorites.toggle(2)
    expect(favorites.isFavorite(2)).toBe(false)
  })

  it('reads stored favorites and ignores a damaged value', () => {
    localStorage.setItem(STORAGE_KEY, '[3,"x",4]')
    expect(useFavoritesStore().ids).toEqual([3, 4])

    localStorage.setItem(STORAGE_KEY, 'not json')
    setActivePinia(createPinia())
    expect(useFavoritesStore().ids).toEqual([])
  })

  it('fetches a page and forgets articles that no longer exist', async () => {
    localStorage.setItem(STORAGE_KEY, '[1,2]')
    const list = vi.spyOn(api, 'listArticles').mockResolvedValue({
      items: [makeListItem({ id: 1 })],
      total: 1,
      page: 1,
      size: 20,
    })
    const favorites = useFavoritesStore()

    await favorites.fetchPage(1)

    expect(list).toHaveBeenCalledWith({ ids: '1,2', size: 20 })
    expect(favorites.articles.map((a) => a.id)).toEqual([1])
    expect(favorites.ids).toEqual([1])
  })

  it('does not call the API when there are no favorites', async () => {
    const list = vi.spyOn(api, 'listArticles')

    await useFavoritesStore().fetchPage(1)

    expect(list).not.toHaveBeenCalled()
  })
})
